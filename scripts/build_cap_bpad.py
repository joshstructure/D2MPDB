"""Build the Blockpad (.bpad) editions of the three distilled cap-design worksheets.

The Mathcad generator (scripts/build_cap_mathcad.py) holds the equation lists. This script walks the same blocks
(`sheet_head + sheet_stations + sheet_tail`), translates each equation to Blockpad syntax (scripts/bpad_sheet.py) and
writes one standalone document per cap with one report each. Region vectors (N, P, B), the five station vectors
(S, N, P, B, M) and the face vectors become scalars, because Blockpad has no vector variables; the visible equations
are written for region N and station S, the others sit in collapsed sections.

Before anything is written, every definition is evaluated by the independent Blockpad-syntax evaluator
(BpEngine) and compared with the cap tool (build_cap_mathcad.comparisons, plus branch-coverage rows) and with the
verified Mathcad environment. The build stops on any mismatch.

    python scripts/build_cap_bpad.py                       # write cap_bpad/*.bpad, fragments/, preview/, verification.json
    python scripts/build_cap_bpad.py --skip-mathcad        # skip the (slow) comparison with the Mathcad environment
    python scripts/build_cap_bpad.py --journal [path]      # journal edition into cap_bpad/journal/ (live references, coherence gate)
"""
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pier_cap import figure_data as figs  # noqa: E402  (the numbers the figures need; no SVG renderer)
from pier_cap.transverse import scheduled_bars  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402
from scripts import build_cap_mathcad as bm  # noqa: E402
from scripts.mathcad_sheet import U  # noqa: E402

OUT_DIR = ROOT / 'cap_bpad'
SIDE_BY_KEY = {
    'end_bent_1': ('CapDesignEndBentOne', 'End Bent 1 Cap Design - Distilled', 'End Bent 1 Cap Design.bpad'),
    'end_bent_2': ('CapDesignEndBentTwo', 'End Bent 2 Cap Design - Distilled', 'End Bent 2 Cap Design.bpad'),
    'pier': ('CapDesignPier', 'Pier Cap Design - Distilled', 'Pier Cap Design.bpad'),
}
TOL = bm.TOL
REGION_TAGS = list(bm.REGIONS)                   # N P B
STATION_TAGS = list(bm.TAGS)                     # S N P B M
REGION_D = {'A_s': 'As', 'd_c': 'dc', 'M_u': 'Mu', 'M_I': 'MI', 'S_p': 'SP'}      # region vectors that map onto existing names
STATION_BASE = {'x_st': 'x', 'M_st': 'M', 'V_st': 'V', 'N_st': 'N', 'T_st': 'T'}
SKIPPED_D = {'Region', 'St', 'Face', 'DC_all', 'CheckGood', 'CheckNoGood', 'Limit', 'ymax'}
PAGE_BREAK_BEFORE = {3, 8, 12}
EXTRA_PROVENANCE = ('Blockpad edition written by scripts/build_cap_bpad.py from the same case; every definition was '
                    'evaluated independently and compared with the cap tool to 1 part in 10⁹.')
REGION_NOTE = ('Regions: N (top steel), P (bottom steel at piles), B (bottom steel between piles, added bars). Equations below '
               'are shown for region N; regions P and B repeat them in the collapsed section and the table.')
FLAG_UNITS = {'tor': None, 'simp': None, 'crk': None}
CHECK_WHERE = {
    'DC_shear': 'S', 'DC_LN': 'N', 'DC_LP': 'P', 'DC_LB': 'B', 'DC_minAv': 'M', 'DC_sp': 'governing interval',
    'DC_tamax': 'all faces (largest)', 'DC_tsmax': 'all faces (largest)', 'DC_skin': 'skin bars', 'DC_hk': 'governing hook',
}
REGION_WHERE = {'N': 'N (top steel)', 'P': 'P (bottom, piles)', 'B': 'B (bottom, between piles)'}


class BuildError(AssertionError):
    pass


def vector_literal(tree):
    """The numbers (or strings) of the first row()/col() literal inside a parse tree."""
    if tree[0] == 'call' and tree[1] in ('row', 'col'):
        out = []
        for a in tree[2]:
            if a[0] in ('num', 'str'):
                out.append(a[1])
            elif a[0] == 'neg' and a[1][0] == 'num':
                out.append(-a[1][1])
            else:
                raise BuildError('vector literal holds an expression')
        return out
    for part in tree[1:]:
        if isinstance(part, tuple):
            found = vector_literal(part)
            if found is not None:
                return found
        elif isinstance(part, list):
            for p in part:
                if isinstance(p, tuple):
                    found = vector_literal(p)
                    if found is not None:
                        return found
    return None


def to_u(q):
    """Mathcad-environment value of a Blockpad quantity (angles are plain radians there)."""
    if isinstance(q, bs.Q):
        return U(q.v, (q.d[0], q.d[1]))
    return q


class Sheet:
    """One cap's report: walks the Mathcad blocks and writes the native elements."""
    journal = None                                  # a JournalContext in the journal edition (live references), else None

    def __init__(self, cap, ctx, blocks, report_name, title):
        self.cap, self.ctx, self.blocks = cap, ctx, blocks
        self.e = ctx.e
        self.name = report_name
        self.doc = bs.new_document()
        self.rep = bs.new_report(self.doc, report_name, title)
        self.n_faces = len(ctx.faces['rows'])
        self.family = {}
        self.tags = {'r': REGION_TAGS, 'k': STATION_TAGS, 'f': [str(i + 1) for i in range(self.n_faces)]}
        self.cur = {'r': 'N', 'k': 'S', 'f': '1'}
        self.scalar_map, self.vector_map = {}, {}
        self.station_names = set()                  # scalars that depend on the five station values
        self.sec, self.sub = 0, ''
        self.pending_regions, self.pending_stations, self.pending_faces = [], [], []
        self.region_rows = []
        self.in_fig3_data = False
        self.deferred = []                          # (canvas, fill(engine)) pairs drawn once the engine exists
        self.canvases = {}
        self.chart_names = []
        self.key_text = ''
        self.after_plot = False
        self.skin = bool(self.e.value('Skin_required'))
        self.hook = ctx.hook is not None
        self.extra_provenance = EXTRA_PROVENANCE          # appended to the 'Distilled from' paragraph

    # -- scalar naming
    def register(self, name, family):
        self.family[name] = family
        names = [self.sname(name, t) for t in self.tags[family]]
        self.vector_map[name] = names
        if family == 'k':
            self.station_names.update(names)

    def sname(self, base, tag):
        fam = self.family[base]
        if fam == 'r' and base in REGION_D:
            return f'{REGION_D[base]}_{tag}'
        if fam == 'k':
            base = STATION_BASE.get(base, base)
        return f'{bs.bp_name(base)}_{tag}'

    def scal(self, base, idx):
        fam = self.family.get(base)
        if fam is None:
            return None
        if idx is None:
            return [self.sname(base, t) for t in self.tags[fam]]
        if isinstance(idx, str):
            return self.sname(base, self.cur[fam])
        return self.sname(base, self.tags[fam][idx])

    def formula_of(self, tree):
        text = bs.bp_formula(tree, self.scal)
        if self.journal is not None:
            text = qualify_bar_calls(text)
        return text

    # -- equations
    def eq(self, parent, formula, caption='', style=None, show_result=True, inline=False):
        return bs.equation(parent, formula, caption, style=style, show_result=show_result, inline=inline)

    def item_formula(self, name, tree, unit):
        text = f'{name} = {self.formula_of(tree)}'
        u = bs.bp_unit(unit)
        return text + (f' to {u}' if u else '')

    def v_formula(self, item, tag):
        self.cur[item.index] = tag
        return self.item_formula(self.sname(item.name, tag), item.tree, item.unit)

    # -- plain blocks
    def do_title(self, blk):
        bs.para(self.rep, 'D2 I-95 PEDESTRIAN BRIDGE', fontsize=16, fontweight='bold', spacingafter=2)
        bs.para(self.rep, blk.payload, fontsize=14, fontweight='bold', spacingafter=6)

    def do_h1(self, blk):
        self.flush()
        self.sec = int(blk.payload.split('.')[0])
        self.sub = ''
        bs.heading(self.rep, blk.payload, page_break=self.sec in PAGE_BREAK_BEFORE)
        if self.journal is not None and self.sec == 2:
            bs.para(self.rep, JOURNAL_SECTION2)

    def do_h2(self, blk):
        self.flush()
        self.sub = blk.payload.split(' ')[0].replace('.', '')
        bs.subheading(self.rep, blk.payload)

    def do_p(self, blk):
        text = blk.payload
        if text.startswith('Figure 3 data'):
            self.in_fig3_data = True
            return
        if text.startswith('Distilled from'):
            text = text + ' ' + self.extra_provenance
        elif text.startswith('Tool status:'):
            text = text.replace('Inputs are highlighted yellow; key results are boxed.',
                                'Inputs are highlighted amber; distilled results are the green tables.')
        elif text.startswith('Regions r:'):
            text = REGION_NOTE
        elif text.startswith('Faces and directions'):
            text = text.replace('; index f.', '. Faces are numbered 1 to %d in the tables below.' % self.n_faces)
        bs.para(self.rep, text)

    def do_note(self, blk):
        text = blk.payload
        if text.startswith('Columns, left to right'):
            return                                   # the Blockpad tables carry their own headers
        if text.startswith('Check numbers:'):
            self.key_text = text
            bs.note(self.rep, text)
            return
        if self.after_plot:
            bs.note(self.rep, text, background='#F1F5FA')
        else:
            bs.note(self.rep, text)

    def do_bullets(self, blk):
        for item in blk.payload:
            bs.para(self.rep, '• ' + item, spacingafter=4)

    def do_fig(self, blk):
        fig1 = blk.payload.endswith('elevation')
        name = 'Figure1Elevation' if fig1 else 'Figure2Section'
        cv = bs.canvas(self.rep, name, 'Cap elevation' if fig1 else 'Cap section between piles', 3.7 if fig1 else 3.8)
        self.canvases[name] = cv
        self.deferred.append((cv, (lambda eng, cv=cv, f1=fig1: self.draw_elevation(cv) if f1 else self.draw_section(cv, eng))))
        bs.note(self.rep, blk.opts['caption'])

    def do_plot(self, blk):
        self.in_fig3_data = False
        self.after_plot = True
        names = [dc for dc, _, _, _ in self.expanded_checks()]
        self.chart_names = names
        ymax = 'DC_ymax = Max(1.2, 1.1*Max(' + ', '.join(names) + '))'
        self.eq(self.rep, ymax, 'vertical scale of Figure 3')
        cv = bs.canvas(self.rep, 'DCChart', 'D/C by check', 3.2)
        self.canvases['DCChart'] = cv
        self.deferred.append((cv, lambda eng, cv=cv: self.draw_chart(cv, eng)))
        bs.note(self.rep, 'Figure 3. Demand/capacity ratio of each distilled check (stems) against the 1.0 limit. The stems are live '
                          'formulas of the check ratios: a stem turns red when its ratio passes 1.0.')

    # -- inputs
    def do_inputs(self, blk):
        bs.para(self.rep, blk.opts['title'], fontweight='bold', spacingbefore='4', spacingafter='3', keepwithnext='True')
        for it in blk.payload:
            self.input_item(it)

    def input_item(self, it):
        name = bs.bp_name(it.name)
        if self.journal is not None and it.name in self.journal.refs:      # journal edition: a live reference, not a literal
            owner, unit = self.journal.refs[it.name]
            self.scalar_map[it.name] = name
            self.eq(self.rep, f'{name} = {owner}' + (f' to {unit}' if unit else ''), f'{REFERENCE_CAPTION} {owner}')
            return
        formula = f'{name} = {self.formula_of(it.tree)}'
        caption = it.caption
        if self.journal is not None and it.name in self.journal.keep:
            caption = self.journal.keep[it.name]['reason']
        self.scalar_map[it.name] = name
        self.eq(self.rep, formula, caption, style='Required Input', show_result=False, inline=bool(caption) and len(caption) <= 45)

    # -- eqs / rows
    def do_eqs(self, blk):
        items = blk.payload
        if self.in_fig3_data:
            return
        if any(it.kind == 'input' for it in items):
            self.station_inputs_table(items)
            return
        for it in items:
            self.item(it)
        self.flush()

    def do_row(self, blk):
        items = blk.payload
        if self.in_fig3_data:
            return
        names = {it.name or it.expr for it in items}
        if any(it.kind == 'input' and it.name == 'A_tp' for it in items):
            self.face_inputs_table(items)
            return
        if all(it.kind == 'show' for it in items):
            exprs = [it.expr for it in items]
            if exprs and exprs[0] == 'St':
                self.station_results_tables()
            elif exprs and exprs[0] == 'Face':
                self.face_results_table()
            return
        for it in items:
            self.item(it)
        self.flush()

    def item(self, it):
        k = it.kind
        if k == 'range' or k == 'show':
            return
        if k == 'eq':
            return self.do_E(it)
        if k == 'def':
            return self.do_D(it)
        if k == 'idef':
            return self.do_V(it)
        raise BuildError(f'unhandled item {k} {it.name}')

    def do_E(self, it):
        if it.name == 'Status':
            return                                   # replaced below with the Blockpad strings
        name = bs.bp_name(it.name)
        self.scalar_map[it.name] = name
        self.eq(self.rep, self.item_formula(name, it.tree, it.unit), it.caption)
        if it.name == 'DC_dist':
            self.summary_extras()

    def do_D(self, it):
        n = it.name
        if n in ('A_bar', 'd_bar'):
            _, formula, caption = bar_function(it)
            if self.journal is not None:                      # journal edition: the tables live in CapDesignBasis
                if n == 'A_bar':
                    bs.note(self.rep, BAR_TABLE_NOTE)
                return
            self.eq(self.rep, formula, caption)
        elif n in REGION_D:
            self.register(n, 'r')
        elif n in SKIPPED_D:
            pass
        else:
            raise BuildError(f'unhandled definition {n}')

    def do_V(self, it):
        fam = it.index
        if fam not in ('r', 'k', 'f'):
            raise BuildError(f'unhandled range {fam} for {it.name}')
        self.register(it.name, fam)
        first = self.tags[fam][0]
        self.eq(self.rep, self.v_formula(it, first), it.caption, show_result=it.show)
        rest = [(t, self.v_formula(it, t)) for t in self.tags[fam][1:]]
        if fam == 'r':
            self.pending_regions.append((it, rest))
            self.region_rows.append(it)
        elif fam == 'k':
            self.pending_stations.append((it, rest))
        else:
            self.pending_faces.append((it, rest))

    def flush(self):
        """Hidden sections for the other regions / stations / faces collected since the last flush, and the region table."""
        if self.pending_regions:
            bs.note(self.rep, 'Regions P and B: the same equations, collapsed.')
            sec = bs.section(self.rep, f'RegionsPB_Sec{self.sec}')
            for it, rest in self.pending_regions:
                for _, formula in rest:
                    self.eq(sec, formula, it.caption, show_result=it.show)
            rows = []
            for it, _ in self.pending_regions:
                unit = bs.bp_unit(it.unit)
                label = it.caption + (f' ({unit})' if unit else '')
                rows.append([label] + [('formula', self.sname(it.name, t) + (f' to {unit}' if unit else '')) for t in REGION_TAGS])
            bs.table(self.rep, f'Sec{self.sec}Regions', ['Quantity', 'N', 'P', 'B'], rows, [280, 80, 80, 80], 'output')
            self.pending_regions = []
        if self.pending_stations:
            bs.note(self.rep, 'Stations N, P, B and M: the same equations, collapsed.')
            sec = bs.section(self.rep, f'StationsNPBM_{self.sub}')
            for tag in STATION_TAGS[1:]:
                for it, rest in self.pending_stations:
                    formula = dict(rest)[tag]
                    self.eq(sec, formula, it.caption, show_result=it.show)
            self.pending_stations = []
        if self.pending_faces:
            sec = bs.section(self.rep, 'FacesOthers')
            for it, rest in self.pending_faces:
                for _, formula in rest:
                    self.eq(sec, formula, it.caption, show_result=it.show)
            self.pending_faces = []

    # -- tables
    def station_inputs_table(self, items):
        values = self.ctx_values
        rows = []
        for name, unit, caption in bm.STATION_INPUTS:
            self.register(name, 'k')
            u = bs.bp_unit(unit)
            cells = [f'{bs.bp_name(STATION_BASE.get(name, name))} ({u})']
            for k, tag in enumerate(STATION_TAGS):
                cells.append(('define', f'{self.sname(name, tag)} = {bs.bp_num(values[name][k])} {u}', 'Required Input'))
            cells.append(caption)
            rows.append(cells)
        bs.table(self.rep, 'StationInputs', ['Input'] + STATION_TAGS + ['Meaning'], rows, [70, 98, 98, 98, 98, 98, 120], 'input', font='9')

    def face_inputs_table(self, items):
        by = {it.name: it for it in items}
        labels = vector_literal(by['Face'].tree)
        a_tp, s_tp = vector_literal(by['A_tp'].tree), vector_literal(by['s_tp'].tree)
        self.register('A_tp', 'f')
        self.register('s_tp', 'f')
        self.face_labels = labels
        rows = []
        for i, label in enumerate(labels):
            tag = self.tags['f'][i]
            rows.append([label, ('define', f'{self.sname("A_tp", tag)} = {bs.bp_num(a_tp[i])} in^2/ft', 'Required Input'),
                         ('define', f'{self.sname("s_tp", tag)} = {bs.bp_num(s_tp[i])} in', 'Required Input')])
        bs.table(self.rep, 'FaceInputs', ['Face', 'A_tp (in^2/ft)', 's_tp (in)'], rows, [170, 175, 175], 'input')

    def station_results_tables(self):
        rows = []
        for k, tag in enumerate(STATION_TAGS):
            rows.append([bm.LABELS[k], ('formula', f'V_r_{tag} to kip'), ('formula', f'DC_V_{tag}'),
                         ('formula', f'F_req_{tag} to kip'), ('formula', f'F_cap_{tag} to kip'), ('formula', f'DC_L_{tag}')])
        bs.table(self.rep, 'StationResults', ['Station', 'V_r (kip)', 'shear D/C', 'F_req (kip)', 'F_cap (kip)', 'tension D/C'], rows,
                 [100, 85, 80, 85, 85, 85], 'output')
        rows = []
        for k, tag in enumerate(STATION_TAGS):
            rows.append([bm.LABELS[k], ('formula', f'β_{tag}'), ('formula', f'θ_{tag} to deg'), ('formula', f'V_c_{tag} to kip'),
                         ('formula', f'V_s_{tag} to kip'), ('formula', f'ε_s_{tag}'), ('formula', f'tor_{tag}'),
                         ('formula', f'simp_{tag}'), ('formula', f'crk_{tag}')])
        bs.table(self.rep, 'StationDetails', ['Station', 'β', 'θ (deg)', 'V_c (kip)', 'V_s (kip)', 'ε_s', 'tor', 'simp', 'crk'], rows,
                 [80, 50, 60, 65, 65, 55, 40, 45, 45], 'output', font='9')

    def face_results_table(self):
        rows = []
        for i, label in enumerate(self.face_labels):
            tag = self.tags['f'][i]
            rows.append([label, ('formula', f'A_tp_{tag} to in^2/ft'), ('formula', f's_tp_{tag} to in'),
                         ('formula', f'DC_ta_{tag}'), ('formula', f'DC_ts_{tag}')])
        bs.table(self.rep, 'FaceResults', ['Face', 'A_tp (in^2/ft)', 's_tp (in)', 'area D/C', 'spacing D/C'], rows,
                 [140, 100, 90, 95, 95], 'output')

    # -- summary
    def expanded_checks(self):
        out = []
        for name, rows, text in bm.dc_checks(self.skin, self.hook):
            if rows == 3:
                for t in REGION_TAGS:
                    out.append((f'{name}_{t}', 'Chk_' + name[3:] + f'_{t}', text, REGION_WHERE[t]))
            else:
                out.append((name, 'Chk_' + name[3:], text, CHECK_WHERE[name]))
        return out

    def summary_extras(self):
        self.eq(self.rep, 'Status = If(DC_dist <= 1, "✓ All Checks Pass", "⊗ There are FAILURES")', 'distilled numerical checks only',
                style='Result only')
        checks = self.expanded_checks()
        sec = bs.section(self.rep, 'Checks')
        for dc, chk, _, _ in checks:
            self.eq(sec, f'{chk} = If({dc} <= 1, "✓ PASS", "⊗ FAIL")')
        rows = [[text, where, ('formula', dc), ('formula', chk)] for dc, chk, text, where in checks]
        rows.append(['OVERALL', 'all checks', ('formula', 'DC_dist'), ('formula', 'Status')])
        bs.table(self.rep, 'Summary', ['Check', 'Region/station', 'D/C', 'Result'], rows, [200, 150, 80, 90], 'output')

    # -- figures
    def draw_elevation(self, cv):
        d = figs._data(self.e)
        stations = figs.governing_stations(self.e)
        W = 6.5
        x0, k = 0.25, 6.0 / d['L']
        cap_top = 2.0
        cap_bot = cap_top - d['h'] * k
        X = lambda x: x0 + x * k
        Y = lambda y: cap_bot + y * k
        cv.label(0.15, 3.5, 'CAP ELEVATION', color=bs.INK, size=9, bold=True)
        STUB, half = 0.45, d['D_pile'] / 2
        for c in d['piles']:
            xa, xb = X(c - half), X(c + half)
            cv.line([(xa, cap_bot), (xa, cap_bot - STUB), (xb, cap_bot - STUB), (xb, cap_bot)], bs.GREY, 1.0)
        cv.rect(X(0), cap_bot, X(d['L']), cap_top, bs.INK, 1.8)
        for c in d['piles']:
            cv.rect(X(c - half), Y(0), X(c + half), Y(d['embed']), bs.GREY, 0.7)
        y0, y1 = Y(d['C_b'] + d['hoop_d'] / 2), Y(d['h'] - d['C_t'] - d['hoop_d'] / 2)
        for bar in d['bars']:
            if bar['kind'] == 'hoop':
                cv.line([(X(bar['station_in']), y0), (X(bar['station_in']), y1)], bs.BLUE, 0.6)
        for bar in d['bars']:
            if bar['kind'] != 'hoop':
                cv.line([(X(bar['station_in']), y0), (X(bar['station_in']), y1)], bs.TEAL, 0.9)
        seen = set()
        for bar in d['longitudinal']:
            key = (bar['kind'], round(bar['y'], 3), round(bar['left'], 3), round(bar['right'], 3))
            if bar['additional'] or bar['kind'] == 'Skin' or key in seen:
                continue
            seen.add(key)
            cv.line([(X(bar['left']), Y(bar['y'])), (X(bar['right']), Y(bar['y']))], bs.INK, 1.4)
        for pts in d['hooks']:
            keep = pts[::3] + ([pts[-1]] if (len(pts) - 1) % 3 else [])
            cv.line([(X(x), Y(y)) for x, y in keep], bs.ORANGE, 2.0)
        for c in d['bearings']:
            x = X(c)
            cv.rect(x - 0.14, cap_top, x + 0.14, cap_top + 0.05, bs.GREY, 1.2)
            cv.line([(x, cap_top + 0.42), (x, cap_top + 0.07)], bs.GREY, 1.0)
            cv.line([(x - 0.04, cap_top + 0.14), (x, cap_top + 0.07), (x + 0.04, cap_top + 0.14)], bs.GREY, 1.0)
        bracket = cap_top + 0.62
        for r in d['runs']:
            a, b = X(r['first']), X(r['end'])
            color = bs.BLUE if r['kind'] == 'hoop' else bs.TEAL
            cv.line([(a, bracket - 0.06), (a, bracket), (b, bracket), (b, bracket - 0.06)], color, 1.0)
            cv.label((a + b) / 2 - 0.028 * len(r['id']), bracket + 0.05, r['id'], color=color, size=8, bold=True)
        top = [t for t in stations if t['face'] == 'top']
        bottom = [t for t in stations if t['face'] != 'top']
        for group, is_top in ((top, True), (bottom, False)):
            xs = [X(t['x_in']) for t in group]
            levels = stagger(xs, 0.25)
            for t, x, lv in zip(group, xs, levels):
                if is_top:
                    cy = cap_top + 1.15 + 0.25 * lv
                    cv.line([(x, cy - 0.09), (x, cap_bot - 0.05)], bs.ROSE, 1.0)
                else:
                    cy = cap_bot - 0.30 - 0.26 * lv
                    cv.line([(x, cap_top + 0.05), (x, cy + 0.09)], bs.ROSE, 1.0)
                cv.circle(x, cy, 0.09, '#FFFFFF', bs.ROSE, 1.0)
                cv.label(x - 0.027, cy - 0.035, t['tag'], color=bs.ROSE, size=8, bold=True)
        cv.label(0.15, 0.1, 'hoop (blue) | pile U (teal) | longitudinal (black) | added bar (orange) | bearing (gray) | circle: governing station',
                 color=bs.INK, size=8)

    def draw_section(self, cv, eng):
        d = figs._data(self.e)
        R = self.name
        b, h = d['b'], d['h']
        k = 3.0 / b
        x0, bottom = 2.1, 0.65
        right, top = x0 + 3.0, bottom + h * k
        X = lambda x: x0 + x * k
        Y = lambda y: bottom + y * k
        cv.label(0.15, 3.58, 'SECTION BETWEEN PILES', color=bs.INK, size=9, bold=True)
        cv.rect(x0, bottom, right, top, bs.INK, 1.6)
        dv = d['hoop_d']
        xa, xb = d['C_s'] + dv / 2, b - d['C_s'] - dv / 2
        ya, yb = d['C_b'] + dv / 2, h - d['C_t'] - dv / 2
        cv.rect(X(xa), Y(ya), X(xb), Y(yb), bs.BLUE, max(dv * k * 72, 1.5))
        top_bars = [q for q in d['section'] if q['kind'].startswith('Top')]
        bot_bars = [q for q in d['section'] if q['kind'].startswith('Bottom')]
        add_bars = [q for q in d['section'] if q['additional']]
        skin_bars = [q for q in d['section'] if q['kind'] == 'Skin']
        d_top = figs._centroid_y(top_bars)
        y_bot = figs._centroid_y(bot_bars + add_bars)
        for yc in (d_top, y_bot):
            cv.line([(x0 - 0.3, Y(yc)), (right + 0.3, Y(yc))], bs.ROSE, 0.7)
        for q in d['section']:
            color = bs.ORANGE if q['additional'] else bs.GREY if q['kind'] == 'Skin' else bs.INK
            cv.circle(X(q['x']), Y(q['y']), q['d'] / 2 * k, color, color, 0.5)
        mid_y = (top + bottom) / 2
        dn, db = eng.get('d_N'), eng.get('d_B')
        shown = lambda q: eng.format_value(q, 'in')
        hx, bx, nx = x0 - 1.9, x0 - 1.05, x0 - 0.35                    # offsets of the h, d_B and d_N dimension lines
        cv.dim((x0, top), (x0, bottom), (hx, mid_y), f'{R}.h', shown(eng.get('h')), '#5D6F80')
        cv.dim((x0, top), (x0, Y(y_bot)), (bx, (top + Y(y_bot)) / 2), f'{R}.d_B', shown(db), bs.ROSE)
        cv.dim((x0, bottom), (x0, Y(d_top)), (nx, (bottom + Y(d_top)) / 2), f'{R}.d_N', shown(dn), bs.ROSE)
        cv.dim((x0, bottom), (right, bottom), ((x0 + right) / 2, bottom - 0.32), f'{R}.b', shown(eng.get('b')), '#5D6F80')
        cv.label(hx - 0.04, top + 0.07, 'h', color='#5D6F80', size=9, bold=True)
        cv.label(bx - 0.14, top + 0.07, 'd (B)', color=bs.ROSE, size=9, bold=True)
        cv.label(nx - 0.14, Y(d_top) + 0.07, 'd (N)', color=bs.ROSE, size=9, bold=True)
        cv.label(x0 - 0.04, bottom - 0.52, 'b', color='#5D6F80', size=9, bold=True)
        lx = right + 0.2
        nt = min(top_bars, key=lambda q: (-q['y'], -q['x']))
        cv.line([(X(nt['x']) + nt['d'] / 2 * k, Y(nt['y'])), (lx - 0.05, Y(nt['y']))], bs.INK, 0.6)
        cv.label(lx, Y(nt['y']) - 0.04, 'top steel (N)', color=bs.INK, size=8)
        cont = [q for q in bot_bars if not q['additional']]
        pb = max(cont, key=lambda q: q['x'])
        ly = bottom + 0.62
        cv.line([(X(pb['x']), Y(pb['y']) - pb['d'] / 2 * k), (lx - 0.05, ly)], bs.INK, 0.6)
        cv.label(lx, ly - 0.04, 'bottom steel (P)', color=bs.INK, size=8)
        if add_bars:
            ab = max(add_bars, key=lambda q: q['x'])
            ly2 = bottom + 0.30
            cv.line([(X(ab['x']), Y(ab['y']) - ab['d'] / 2 * k), (lx - 0.05, ly2)], bs.ORANGE, 0.6)
            cv.label(lx, ly2 - 0.04, 'added span bars (B)', color=bs.ORANGE, size=8)
        if skin_bars:
            sb = sorted([q for q in skin_bars if q['x'] > b / 2], key=lambda q: q['y'])
            sb = sb[len(sb) // 2] if sb else skin_bars[0]
            cv.line([(X(sb['x']) + sb['d'] / 2 * k, Y(sb['y'])), (lx - 0.05, Y(sb['y']))], bs.GREY, 0.6)
            cv.label(lx, Y(sb['y']) - 0.04, 'skin', color=bs.GREY, size=8)
        hy = mid_y + 0.45
        cv.line([(X(xb), hy), (lx - 0.05, hy)], bs.BLUE, 0.6)
        cv.label(lx, hy - 0.04, 'hoop', color=bs.BLUE, size=8)

    def draw_chart(self, cv, eng):
        R = self.name
        names = self.chart_names
        n = len(names)
        ymax = eng.get('DC_ymax').v
        x_lo, x_hi, y_lo, y_hi = 0.6, 6.3, 0.5, 2.9
        height = y_hi - y_lo
        cv.label(0.6, 3.05, 'D/C by check — blue within 1.0, red over 1.0', color=bs.INK, size=9, bold=True)
        cv.line([(x_lo, y_lo), (x_hi, y_lo)], bs.INK, 1.2)
        cv.line([(x_lo, y_lo), (x_lo, y_hi)], bs.INK, 1.2)
        limit_y = y_lo + height / ymax
        cv.plot([f'{x_lo}', f'{x_hi}'], [f'0.5+2.4/{R}.DC_ymax'] * 2, bs.GREY, 0.9, [(x_lo, limit_y), (x_hi, limit_y)])
        cv.label(x_lo + 0.08, limit_y + 0.04, '1.0 limit', color=bs.GREY, size=8)
        cv.label(0.38, y_lo - 0.06, '0', color=bs.INK, size=8)
        cv.label(0.12, y_hi - 0.06, formula=f'{R}.DC_ymax', color=bs.INK, size=8, shown=f'{ymax:.3f}')
        for j, name in enumerate(names, 1):
            x = x_lo + (x_hi - x_lo) * j / (n + 1)
            xs = f'{x:.3f}'.rstrip('0').rstrip('.')
            value = eng.get(name).v
            qn = f'{R}.{name}'
            blue = [(x, y_lo), (x, y_lo + height * value / ymax)] if value <= 1 else []
            red = [(x, y_lo), (x, y_lo + height * value / ymax)] if value > 1 else []
            cv.plot([xs, xs], ['0.5', f'0.5+2.4*If({qn} <= 1, {qn}, null)/{R}.DC_ymax'], bs.BLUE, 2.2, blue)
            cv.plot([xs, xs], ['0.5', f'0.5+2.4*If({qn} > 1, {qn}, null)/{R}.DC_ymax'], bs.RED, 2.2, red)
            cv.label(x - 0.025 * len(str(j)) - 0.01, y_lo - 0.2, str(j), color=bs.INK, size=7)


def stagger(xs, gap):
    """Lowest level for each tag so that tags on one level stay `gap` apart."""
    last, levels = [], [0] * len(xs)
    for i in sorted(range(len(xs)), key=lambda i: xs[i]):
        for level, x in enumerate(last):
            if xs[i] - x >= gap:
                last[level] = xs[i]
                levels[i] = level
                break
        else:
            last.append(xs[i])
            levels[i] = len(last) - 1
    return levels


# ----------------------------------------------------------------------------- verification helpers
def split_list(text):
    """Top-level items of the text inside [...]."""
    items, depth, cur = [], 0, ''
    for ch in text:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == ',' and depth == 0:
            items.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def plot_items(formula):
    m = re.fullmatch(r'PlotLines\(\[(.*)\],\[(.*)\]\)', formula)
    if not m:
        raise BuildError(f'unreadable plot formula {formula!r}')
    return split_list(m.group(1)), split_list(m.group(2))


def adapter_env(sheet, eng):
    """An environment shaped like the Mathcad one, filled from the Blockpad evaluation."""
    env = {}
    for mc, bp in sheet.scalar_map.items():
        env[mc] = to_u(eng.get(bp))
    for mc, names in sheet.vector_map.items():
        env[mc] = [to_u(eng.get(n)) for n in names]
    fn = BASIS_NAME + '.' if getattr(sheet, 'journal', None) is not None else ''      # journal edition: CapDesignBasis.Ab(k)
    env['A_bar'] = [to_u(eng.evaluate(f'{fn}Ab({k})')) for k in range(12)]
    env['d_bar'] = [to_u(eng.evaluate(f'{fn}Db({k})')) for k in range(12)]
    return env


def compare_envs(mine, theirs):
    """Compare the quantities both environments hold; returns (count, mismatches)."""
    count, bad = 0, []

    def one(label, a, b):
        nonlocal count
        if isinstance(a, U) and isinstance(b, U):
            count += 1
            same_dims = abs(a.d[0] - b.d[0]) < 1e-9 and abs(a.d[1] - b.d[1]) < 1e-9
            if not same_dims or not abs(a.v - b.v) <= TOL * max(abs(b.v), 1e-6):
                bad.append((label, a, b))

    for name, a in mine.items():
        if name not in theirs:
            continue
        b = theirs[name]
        if isinstance(a, list) and isinstance(b, list):
            for i, (x, y) in enumerate(zip(a, b)):
                one(f'{name}[{i}]', x, y)
        else:
            one(name, a, b)
    return count, bad


# ----------------------------------------------------------------------------- build
def prepare(cap, e=None, report=None, revision=None):
    """The evaluated case, its report link and the block list; `e`, `report` and `revision` replace the files
    (an in-memory notebook case, a report-link dict as bm.report_info returns, the package revision text)."""
    e = bm.evaluate_cap(cap) if e is None else e
    rep = bm.report_link(cap, e) if report is None else report
    rev = bm.notebook_revision() if revision is None else revision
    rows = bm.governing_stations(e)
    bm.check_stations(e, rows)
    physical = scheduled_bars(e.case)
    dv, l_cap = e.value('dv', 'in'), e.value('L_cap', 'in')
    values = bm.station_values(e, rows, physical, dv, l_cap)
    ctx = SimpleNamespace(cap=cap, e=e, report=rep, revision=rev, values=bm.input_values(e), rows=rows,
                          spacing=bm.spacing_data(e), faces=bm.face_data(e), hook=bm.hook_data(e))
    blocks = bm.sheet_head(ctx) + bm.sheet_stations(ctx, rows, values) + bm.sheet_tail(ctx, ctx.spacing, ctx.faces, ctx.hook)
    return ctx, blocks, values, physical, dv, l_cap


def build_cap(cap, mathcad_compare=True, e=None, report=None, revision=None, names=None, extra_provenance=None, journal=None):
    """Build and verify one cap's report: (sheet, engine, meta, filename, ctx).

    `e`, `report` and `revision` take an in-memory case instead of the project files (see prepare); `names` is
    (report name, title, filename) in place of SIDE_BY_KEY; `extra_provenance` replaces EXTRA_PROVENANCE.
    `mathcad_compare` builds the Mathcad sheet of the same cap from the project files, so it is for file builds only.
    `journal` is a bpad_sheet.JournalLinks: the journal edition, whose shared inputs are live references to the journal
    and to CapDesignBasis. The coherence gate then runs first and stops the build when a journal value disagrees with
    the cap case; meta['journal'] holds the coherence rows."""
    ctx, blocks, values, physical, dv, l_cap = prepare(cap, e, report, revision)
    e = ctx.e
    report_name, title, filename = names or SIDE_BY_KEY[cap['key']]
    jctx = journal_context(journal, cap, ctx, blocks) if journal is not None else None
    sheet = Sheet(cap, ctx, blocks, report_name, title)
    sheet.journal = jctx
    if extra_provenance is not None:
        sheet.extra_provenance = extra_provenance
    sheet.ctx_values = values
    for blk in blocks:
        getattr(sheet, 'do_' + blk.kind)(blk)
    sheet.flush()
    bs.note(sheet.rep, 'A distilled result of ✓ covers only the recomputed numerical checks; it is not design acceptance. Recalculate in Blockpad after any input change.', size=9)

    rep = sheet.rep
    # ---- (a) syntax and names: the engine is built from the XML that will be written
    eng = new_engine(report_name, jctx)
    n_defs = n_funcs = 0
    for dyn in rep.iter('dynexp'):
        formula = dyn.get('formula')
        body = dyn.find('expbody')
        if body is None or body.text != formula:
            raise BuildError(f'expbody differs from the formula: {formula!r}')
        name = eng.add(formula)
        if name in eng.functions:
            n_funcs += 1
        else:
            n_defs += 1
    if eng.unresolved_calls():
        raise BuildError(f'undefined functions: {eng.unresolved_calls()}')
    eng.all()
    taken = set(eng.defs) | set(eng.functions)
    for name in sorted(taken):
        if re.fullmatch(r'[A-Za-z]{1,3}[0-9]+', name):
            raise BuildError(f'{name} looks like a spreadsheet cell address')
    for el in rep.iter('table', 'canvas', 'textcell', 'section'):
        if el.get('name') in taken:
            raise BuildError(f'{el.tag} name {el.get(chr(110)+chr(97)+chr(109)+chr(101))} is also a definition')
    names = [el.get('name') for el in rep.iter('table', 'canvas', 'textcell', 'section')]
    if len(names) != len(set(names)):
        raise BuildError('duplicate table, canvas, textcell or section name')
    # live canvases are drawn now that values exist
    for cv, fill in sheet.deferred:
        fill(eng)
    for el in rep.iter('plot'):
        xs, ys = plot_items(el.get('formula'))
        for item in xs + ys:
            v = eng.evaluate(item)
            if v is not bs.NULL and (not isinstance(v, bs.Q) or v.d != bs.NODIM):
                raise BuildError(f'plot coordinate {item!r} is not a plain number')
    n_cells = bs.write_caches(rep, eng, report_name)
    for el in rep.iter('c', 'planecontainer', 'lineardim'):
        if el.get('formula'):
            eng.evaluate(el.get('formula'))
    for el in rep.iter():
        if not isinstance(el.tag, str):
            raise BuildError('XML comment in the report')
    check_formula_rules(rep)
    if jctx is not None:
        check_journal_edition(rep, jctx)

    # ---- (b) against the cap tool
    env = adapter_env(sheet, eng)
    shown = bm.comparisons(env, SimpleNamespace(e=e, rows=ctx.rows, spacing=ctx.spacing, faces=ctx.faces, hook=ctx.hook))
    bm.compare(shown, 'Blockpad sheet')

    # ---- (d) branch coverage of the Blockpad station equations
    real, synthetic = bm.coverage_stations(e, ctx.rows), bm.synthetic_stations(e, physical)
    cover = real + synthetic
    cover_rows = [r for _, r in cover]
    for r in ctx.rows + cover_rows:
        if r['exception_applied']:
            raise BuildError(f'{r["id"]}: the direct-region exception applies; it is not distilled')
    unreached = [n for n, hit in bm.branches_reached(ctx.rows + cover_rows).items() if not hit]
    if unreached:
        raise BuildError('branch coverage does not reach: ' + ', '.join(unreached))
    cover_values = bm.station_values(e, cover_rows, physical, dv, l_cap)
    extra = coverage_comparisons(sheet, eng, ctx, cover, cover_rows, cover_values)
    bm.compare(extra, 'Blockpad branch coverage')

    # ---- (c) against the Mathcad sheet
    n_mathcad = None
    if mathcad_compare:
        _, menv = bm.build(cap)
        n_mathcad, bad = compare_envs(env, menv)
        if bad:
            raise BuildError('Blockpad values differ from the Mathcad sheet:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40]))
        mstatus = 'PASS' if menv['Status'] == 'PASS' else 'FAIL'
    else:
        mstatus = None

    # ---- (e) Figure 3 and (f) the Chk strings
    expected = [dc for dc, _, _, _ in sheet.expanded_checks()]
    if sheet.chart_names != expected:
        raise BuildError('Figure 3 stems do not follow dc_checks')
    chart_refs = []
    for el in rep.iter('plot'):
        m = re.search(r'If\((' + re.escape(report_name) + r'\.\w+) <= 1', el.get('formula'))
        if m:
            chart_refs.append(m.group(1).split('.', 1)[1])
    if chart_refs != expected:
        raise BuildError('Figure 3 stems reference different names than dc_checks')
    ratios = [eng.get(n).v for n in expected]
    if eng.get('DC_ymax').v < max(1.2, 1.1 * max(ratios)) - 1e-12:
        raise BuildError('DC_ymax does not reach the largest ratio')
    for dc, chk, _, _ in sheet.expanded_checks():
        want = '⊗ FAIL' if eng.get(dc).v > 1 else '✓ PASS'
        if eng.get(chk) != want:
            raise BuildError(f'{chk} is {eng.get(chk)!r} for ratio {eng.get(dc).v}')
    status = eng.get('Status')
    if status not in ('✓ All Checks Pass', '⊗ There are FAILURES'):
        raise BuildError(f'Status {status!r}')
    if mstatus is not None and (status == '✓ All Checks Pass') != (mstatus == 'PASS'):
        raise BuildError(f'Status {status!r} disagrees with the Mathcad Status {mstatus}')

    meta = dict(report=ctx.report['file'], definitions=n_defs, functions=n_funcs, cells=n_cells, shown=len(shown), coverage=len(extra),
                coverage_real=len(real), coverage_synthetic=len(synthetic), mathcad_values=n_mathcad, status=status,
                stations=[r['id'] for r in ctx.rows], branches=sorted(bm.branches_reached(ctx.rows + cover_rows)),
                comparisons=len(shown) + len(extra))
    if jctx is not None:
        meta['journal'] = jctx.summary()
    return sheet, eng, meta, filename, ctx


def coverage_comparisons(sheet, eng, ctx, cover, cover_rows, cover_values):
    """Station equations for the branch-coverage rows, evaluated by a throwaway engine next to the head definitions."""
    n = len(cover_rows)
    cov = new_engine(sheet.name, sheet.journal)
    for dyn in sheet.rep.iter('dynexp'):
        formula = dyn.get('formula')
        lhs, _ = bs.split_definition(formula)
        base = lhs.split('(')[0]
        if base in sheet.station_names:
            continue
        cov.add(formula)
    tags = [f'C{i}' for i in range(n)]
    stations = {}
    for name, unit, _ in bm.STATION_INPUTS:
        for i, tag in enumerate(tags):
            cov.add(f'{sheet.sname(name, tag)} = {bs.bp_num(cover_values[name][i])} {bs.bp_unit(unit)}')
    v_items = []
    for _, items in bm.station_equation_groups():
        for it in items:
            if it.kind == 'idef':
                v_items.append(it)
    for tag in tags:
        for it in v_items:
            cov.add(sheet.v_formula(it, tag))
    if cov.unresolved_calls():
        raise BuildError(f'coverage engine: undefined functions {cov.unresolved_calls()}')
    env = {'A_vmin': to_u(cov.get('A_vmin'))}
    for it in v_items:
        env[it.name] = [to_u(cov.get(sheet.sname(it.name, tag))) for tag in tags]
    # restore the station scalar names registered for the sheet itself
    return bm.station_comparisons(env, ctx, cover_rows, [label for label, _ in cover], ratio_rows=range(n), prefix='coverage ')


FUNCTION_NAMES = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin',
                  'PlotLines', 'Ab', 'Db'}


def check_formula_rules(rep):
    """No exponent notation, no bare-unit division or multiplication, only the case-sensitive function names."""
    for el in rep.iter():
        formula = el.get('formula')
        if not formula:
            continue
        stripped = re.sub(r'"[^"]*"', '""', formula)
        stripped = re.sub(r'\s+to\s+[A-Za-z0-9^*/ ]+$', '', stripped)
        if re.search(r'(?<![A-Za-z_0-9.])\d+(\.\d+)?[eE][+-]?\d+', stripped):
            raise BuildError(f'exponent notation in {formula!r}')
        if re.search(r'/\s*(in|ft|kip|ksi|ksf|klf|psf|psi|deg|lbf)\b', re.sub(r'\d+(\.\d+)? [a-z]+(\^\d+)?(\*[a-z]+(\^\d+)?)*/[a-z]+(\^\d+)?', '', stripped)):
            raise BuildError(f'bare-unit division in {formula!r}')
        if re.search(r'\*\s*(in|ft|kip|ksi|ksf|klf|psf|psi|deg|lbf)\b', re.sub(r'\d+(\.\d+)? [a-z]+(\^\d+)?(\*[a-z]+(\^\d+)?)+', '', stripped)):
            raise BuildError(f'bare-unit multiplication in {formula!r}')
        for fn in re.findall(r'([A-Za-z_][A-Za-z_0-9]*)\(', stripped):
            lhs, _ = bs.split_definition(formula)
            if fn in FUNCTION_NAMES or (lhs and lhs.startswith(fn + '(')):
                continue
            raise BuildError(f'function {fn} in {formula!r}')
    for p in rep.iter('paragraph'):
        if p.text and ('\n' in p.text or '\r' in p.text):
            raise BuildError('newline in paragraph text')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_outputs(sheet, eng, meta, filename, ctx, cap, out_dir=None):
    """Write the document, fragment and preview sidecar into cap_bpad/ (or `out_dir`); returns the verification entry."""
    out = OUT_DIR if out_dir is None else Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'fragments').mkdir(exist_ok=True)
    (out / 'preview').mkdir(exist_ok=True)
    data = bs.serialize(sheet.doc)
    (out / filename).write_bytes(data)
    (out / 'fragments' / f'{sheet.name}.xml').write_bytes(bs.serialize(sheet.rep, declaration=False).rstrip())
    sidecar = {name: cv.sidecar() for name, cv in sheet.canvases.items()}
    (out / 'preview' / f'{sheet.name}.canvases.json').write_text(json.dumps(sidecar, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
    xml = ctx.e.case['analysis']['xml_audit']
    bpad_file = f'cap_bpad/{filename}' if out_dir is None else f'{out.name}/{filename}'
    return {
        'cap': cap['label'], 'report_file': ctx.report['file'], 'bpad_file': bpad_file, 'report_name': sheet.name,
        'case_sha256': ctx.report['case_sha'], 'formula_sha256': ctx.report['formula_sha'], 'fbmp_file': xml['filename'],
        'fbmp_sha256': xml['sha256'], 'package_revision': ctx.revision, 'stations': meta['stations'],
        'definitions': meta['definitions'], 'functions': meta['functions'], 'cells_and_labels': meta['cells'],
        'tool_comparisons': meta['comparisons'], 'sheet_comparisons': meta['shown'], 'coverage_comparisons': meta['coverage'],
        'coverage_rows_real': meta['coverage_real'], 'coverage_rows_synthetic': meta['coverage_synthetic'],
        'mathcad_values_compared': meta['mathcad_values'], 'branches_reached': meta['branches'], 'status': meta['status'],
        'bpad_sha256': hashlib.sha256(data).hexdigest(),
    }


# ----------------------------------------------------------------------------- journal edition (live references)
BASIS_NAME = 'CapDesignBasis'
BASIS_TITLE = 'Cap Design Basis - shared factors'
JOURNAL_PATH = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
JOURNAL_SUBDIR = 'journal'                                         # cap_bpad/journal/
REVIEW_FILE = 'Cap Design - Journal Edition (review).bpad'
REFERENCE_CAPTION = 'shared journal value —'
JOURNAL_SECTION2 = 'Shared geometry, materials and factors are live references to the journal; the owner is named beside each.'
BAR_TABLE_NOTE = (f'Bar areas and diameters by bar number are the shared functions {BASIS_NAME}.Ab(k) and {BASIS_NAME}.Db(k) '
                  f'({REFERENCE_CAPTION} {BASIS_NAME}); this report defines no bar table of its own.')
REVIEW_BANNER = ('Review copy: the references to BridgeGeometry_2Beam, FBMPEndBent and PierCapDesign resolve only inside the project '
                 'journal (D2_I95_Project_Journal.bpad). Opened on its own, this file shows them as undefined; the values stored in it '
                 'are the journal values at the time of the build.')
BG = 'BridgeGeometry_2Beam'
# Section 2 inputs that become live references: Mathcad name -> (qualified owner in the journal, display unit)
END_BENT_REFS = {
    'b': (f'{BG}.EndBentCap_width', 'in'), 'h': (f'{BG}.EndBentCap_depth', 'in'),
    'C_t': (f'{BG}.EndBent_coverTop', 'in'), 'C_b': (f'{BG}.EndBent_coverBottom', 'in'), 'C_s': (f'{BG}.EndBent_coverSide', 'in'),
    'fc': ('FBMPEndBent.EBSteel_fc', 'ksi'), 'fy': ('FBMPEndBent.EBSteel_fy', 'ksi'), 'Es': ('FBMPEndBent.EBSteel_Es', 'ksi'),
}
PIER_REFS = {
    'b': (f'{BG}.PierCap_width', 'in'), 'h': (f'{BG}.PierCap_ht', 'in'), 'L_cap': (f'{BG}.PierCap_length', 'in'),
    'C_t': ('PierCapDesign.C_t', 'in'), 'C_b': ('PierCapDesign.C_b', 'in'), 'C_s': ('PierCapDesign.C_s', 'in'),
    'fc': ('PierCapDesign.fc', 'ksi'), 'fy': ('PierCapDesign.fy', 'ksi'), 'Es': ('PierCapDesign.Es', 'ksi'),
}
# The cap design constants that no journal report owns: Mathcad name, value, display unit, caption with its code reference.
BASIS_CONSTANTS = [
    ('phi_f', 0.9, None, 'flexure resistance factor, tension-controlled sections, LRFD 5.5.4.2'),
    ('phi_v', 0.9, None, 'shear and torsion resistance factor, normal-weight concrete, LRFD 5.5.4.2'),
    ('phi_a', 0.9, None, 'axial resistance factor, LRFD 5.7.3.5'),
    ('gamma_e', 1, None, 'crack-control exposure factor, Class 1, LRFD 5.6.7'),
    ('lambda_c', 1, None, 'concrete density modification factor, normal weight, LRFD 5.4.2.8'),
    ('s_proj', 12, 'in', 'project spacing limit for face steel, FDOT SDG 4.1.4A–C'),
]
BASIS_REFS = {mc: (f'{BASIS_NAME}.{bs.bp_name(mc)}', unit) for mc, _, unit, _ in BASIS_CONSTANTS}
# Inputs that stay literals although the journal holds a similar quantity: (cap key, Mathcad name) -> why, and what to report.
# 'owner' is the journal definition that is evaluated and reported (never compared) next to the case value.
CAP_LENGTH_REASON = ('cap + cheek cage envelope (D-027: 235 in cap + two 8 in cheeks); '
                     f'{BG}.EndBentCap_length still holds 17 ft 8 in')
KEEP_LITERAL = {
    (key, 'L_cap'): dict(status='literal_incoherent_journal', owner=f'{BG}.EndBentCap_length', unit='in', reason=CAP_LENGTH_REASON)
    for key in ('end_bent_1', 'end_bent_2')
}
LITERAL_STATUSES = ('literal_owner_here', 'literal_incoherent_journal')
INPUT_ORDER = [name for _, group in bm.INPUT_GROUPS for name, _, _ in group]


def references_for(cap_key):
    """{Mathcad name: (qualified owner, unit)} of a cap: its geometry and materials plus the shared basis."""
    refs = dict(PIER_REFS if cap_key == 'pier' else END_BENT_REFS)
    refs.update(BASIS_REFS)
    return refs


def literals_for(cap_key):
    return {name: spec for (key, name), spec in KEEP_LITERAL.items() if key == cap_key}


def qualify_bar_calls(text):
    """Ab(...) / Db(...) -> CapDesignBasis.Ab(...) / CapDesignBasis.Db(...)."""
    return re.sub(r'(?<![\w.])(Ab|Db)\(', BASIS_NAME + r'.\1(', text)


def bar_function(it):
    """(function name, Blockpad definition, caption) of the A_bar / d_bar bar table definition `it`."""
    n = it.name
    vals = vector_literal(it.tree)
    unit = 'in^2' if n == 'A_bar' else 'in'
    expr = f'0 {unit}'
    for k in range(len(vals) - 1, 2, -1):
        expr = f'If(k == {k}, {bs.bp_num(vals[k])} {unit}, {expr})'
    fname = 'Ab' if n == 'A_bar' else 'Db'
    return fname, f'{fname}(k) = {expr}', 'bar area by bar number' if n == 'A_bar' else 'bar diameter by bar number'


def bar_functions(blocks):
    """{'Ab': (definition, caption), 'Db': ...} from the bar tables of a cap's block list."""
    out = {}
    for blk in blocks:
        if blk.kind == 'eqs':
            for it in blk.payload:
                if it.kind == 'def' and it.name in ('A_bar', 'd_bar'):
                    fname, formula, caption = bar_function(it)
                    out[fname] = (formula, caption)
    if sorted(out) != ['Ab', 'Db']:
        raise BuildError('the bar tables A_bar and d_bar were not found in the block list')
    return out


def in_unit(q, unit):
    """The number of a quantity in a display unit (None: it must be a plain number)."""
    if unit is None:
        if q.d != bs.NODIM:
            raise bs.BpError(f'{q!r} is not a plain number')
        return q.v
    u = bs.BpEngine().unit_q(unit)
    q.same(u, f'unit {unit}')
    return q.v / u.v


def clean(v):
    return float(f'{v:.12g}')


def number_text(v):
    return bs.bp_num(clean(v))


class CapBasis:
    """The shared report CapDesignBasis: factors, bar-table functions, discussion box; evaluated and read back."""

    def __init__(self, bars):
        self.bars = bars
        self.doc, self.rep = build_basis_report(bars)
        self.review_rep = build_basis_report(bars, banner=True)[1]
        self.eng = bs.BpEngine(report=BASIS_NAME)
        for dyn in self.rep.iter('dynexp'):
            formula = dyn.get('formula')
            body = dyn.find('expbody')
            if body is None or body.text != formula:
                raise BuildError(f'expbody differs from the formula: {formula!r}')
            self.eng.add(formula)
        if self.eng.unresolved_calls():
            raise BuildError(f'{BASIS_NAME}: undefined functions {self.eng.unresolved_calls()}')
        self.eng.all()
        taken = set(self.eng.defs) | set(self.eng.functions)
        for name in sorted(taken):
            if re.fullmatch(r'[A-Za-z]{1,3}[0-9]+', name):
                raise BuildError(f'{name} looks like a spreadsheet cell address')
        for el in self.rep.iter('table', 'textcell', 'section'):
            if el.get('name') in taken:
                raise BuildError(f'{el.tag} name {el.get("name")} is also a definition')
        check_formula_rules(self.rep)
        self.fragment = bs.serialize(self.rep, declaration=False).rstrip()
        written = bs.ET.fromstring(self.fragment)                    # what the written XML defines, read back
        self.names = set()
        for dyn in written.iter('dynexp'):
            lhs, _ = bs.split_definition(dyn.get('formula'))
            self.names.add(lhs.split('(')[0])
        self.values = {bs.bp_name(mc): self.eng.get(bs.bp_name(mc)) for mc, _, _, _ in BASIS_CONSTANTS}
        self.functions = {f'{BASIS_NAME}.{fname}': formula for fname, (formula, _) in bars.items()}

    def value(self, qualified):
        owner, _, name = qualified.partition('.')
        if owner != BASIS_NAME or name not in self.values:
            raise bs.JournalError(f'{qualified} is not a constant of {BASIS_NAME}')
        return self.values[name]


def build_basis_report(bars, banner=False):
    """(document, report element) of CapDesignBasis; `banner` adds the review-copy notice at the top."""
    doc = bs.new_document()
    rep = bs.new_report(doc, BASIS_NAME, BASIS_TITLE)
    if banner:
        bs.para(rep, REVIEW_BANNER, fontsize='10', textcolor='#8A2B1F', background='#FBE9E5', spacingafter='8')
    bs.para(rep, 'D2 I-95 PEDESTRIAN BRIDGE', fontsize=16, fontweight='bold', spacingafter=2)
    bs.para(rep, BASIS_TITLE, fontsize=14, fontweight='bold', spacingafter=6)
    bs.para(rep, 'Cap design constants that no other journal report owns, written once for the three distilled cap design reports. '
                 'Written by scripts/build_cap_bpad.py --journal; edit the values there, not here.')
    bs.heading(rep, '1. Shared factors and limits')
    for mc, value, unit, caption in BASIS_CONSTANTS:
        bs.equation(rep, f'{bs.bp_name(mc)} = {number_text(value)}' + (f' {unit}' if unit else ''), caption,
                    style='Required Input', show_result=False)
    bs.heading(rep, '2. Bar tables')
    for fname in ('Ab', 'Db'):
        bs.equation(rep, bars[fname][0], bars[fname][1])
    bs.heading(rep, '3. Discussion')
    bs.table(rep, 'BasisDiscussion', ['Discussion'], [
        ['What this is. The factors, the project spacing limit and the bar tables shared by the distilled cap design reports. Geometry '
         'and materials are not repeated here; each cap report reads them from the report that owns them.'],
        ['Read by. CapDesignEndBentOne, CapDesignEndBentTwo and CapDesignPier, as CapDesignBasis.φ_f, CapDesignBasis.φ_v, '
         'CapDesignBasis.φ_a, CapDesignBasis.γ_e, CapDesignBasis.λ, CapDesignBasis.s_proj, CapDesignBasis.Ab(k) and CapDesignBasis.Db(k).'],
        ['Codes. AASHTO LRFD Bridge Design Specifications, 10th edition (2024); FDOT Structures Design Guidelines, January 2026; '
         'article numbers are cited beside each factor.'],
        ['C005. PierCapDesign keeps its own copies of φ_f, φ_v and γ_e under decision D-003 (preserve C005 unchanged). This report '
         'neither reads nor changes them; the pier cap report reads PierCapDesign for its cover and materials and this report for the factors.'],
    ], [620], 'discussion')
    return doc, rep


class JournalContext:
    """What a journal-edition cap build needs: references, kept literals, externals, the basis and the coherence rows."""

    def __init__(self, links, basis, cap_key, refs, keep, rows, externals, units):
        self.links, self.basis, self.cap_key = links, basis, cap_key
        self.refs, self.keep, self.rows, self.externals, self.units = refs, keep, rows, externals, units

    def apply(self, eng):
        for qualified, value in self.externals.items():
            eng.add_external(qualified, value)
        for qualified, formula in self.basis.functions.items():
            eng.add_function_as(qualified, formula)

    def summary(self):
        kept = [r for r in self.rows if r['status'] != 'reference']
        return dict(rows=self.rows, references=sum(r['status'] == 'reference' for r in self.rows), literals=kept, units=self.units)


def new_engine(report_name, jctx=None):
    eng = bs.BpEngine(report=report_name)
    if jctx is not None:
        jctx.apply(eng)
    return eng


def journal_basis(links, blocks):
    """The CapDesignBasis edition for this journal, built from the first cap's bar tables and checked against the others."""
    bars = bar_functions(blocks)
    if links.basis is None:
        links.basis = CapBasis(bars)
    elif links.basis.bars != bars:
        raise BuildError('the bar tables of this cap differ from the ones in CapDesignBasis')
    return links.basis


def journal_context(links, cap, ctx, blocks):
    """The coherence gate: every referenced journal value must equal the cap-case input, else the build stops."""
    basis = journal_basis(links, blocks)
    key = cap['key']
    refs, keep = references_for(key), literals_for(key)
    for name in set(refs) & set(keep):
        raise BuildError(f'{name} is both a reference and a kept literal')
    unknown = [n for n in list(refs) + list(keep) if n not in INPUT_ORDER]
    if unknown:
        raise BuildError(f'not Section 2 inputs: {unknown}')
    rows, bad, externals, units = [], [], {}, {}
    for mc in INPUT_ORDER:
        if mc not in refs and mc not in keep:
            continue
        case = float(ctx.values[mc])
        unit = refs[mc][1] if mc in refs else keep[mc]['unit']
        owner = refs[mc][0] if mc in refs else keep[mc]['owner']
        shown = bs.bp_name(mc)
        units[shown] = unit or ''
        try:
            q = basis.value(owner) if owner.startswith(BASIS_NAME + '.') else links.value(owner)
            journal_value = in_unit(q, unit)
        except bs.BpError as ex:
            bad.append(f'  {shown}: {owner} cannot be evaluated: {ex}')
            continue
        agree = abs(journal_value - case) <= TOL * max(abs(case), 1e-12)
        if mc in refs:
            externals[owner] = q
            if not agree:
                bad.append(f'  {shown} ({cap["label"]}): the case holds {number_text(case)}{" " + unit if unit else ""} but the journal '
                           f'owner {owner} holds {number_text(journal_value)}{" " + unit if unit else ""}')
            rows.append(dict(input=shown, owner=owner, journal_value=clean(journal_value), case_value=clean(case), status='reference',
                             note=f'{REFERENCE_CAPTION} {owner}' + (f' ({unit})' if unit else ' (no unit)')))
        else:
            spec = keep[mc]
            if spec['status'] not in LITERAL_STATUSES:
                raise BuildError(f'{mc}: unknown literal status {spec["status"]}')
            if spec['status'] == 'literal_incoherent_journal' and agree:
                bad.append(f'  {shown} is kept as a literal because {owner} disagreed, but they agree now '
                           f'({number_text(case)} {unit}): make it a reference and remove it from KEEP_LITERAL')
            rows.append(dict(input=shown, owner=owner, journal_value=clean(journal_value), case_value=clean(case), status=spec['status'],
                             note=spec['reason']))
    if bad:
        raise BuildError(f'coherence gate, {cap["label"]}: the journal disagrees with the cap case\n' + '\n'.join(bad))
    return JournalContext(links, basis, key, refs, keep, rows, externals, units)


def check_journal_edition(rep, jctx):
    """No Ab/Db definition and no literal for a referenced name remain, and every CapDesignBasis name is written in its report."""
    defs = {}
    for dyn in rep.iter('dynexp'):
        lhs, rhs = bs.split_definition(dyn.get('formula'))
        if lhs and lhs.split('(')[0] in ('Ab', 'Db'):
            raise BuildError(f'{lhs}: the bar tables are read from {BASIS_NAME} in the journal edition')
        defs[lhs] = rhs
    for mc, (owner, unit) in jctx.refs.items():
        name = bs.bp_name(mc)
        want = owner + (f' to {unit}' if unit else '')
        if defs.get(name) != want:
            raise BuildError(f'{name} is {defs.get(name)!r} in the report; the reference {want!r} is required')
    for el in rep.iter():
        formula = el.get('formula')
        if not formula:
            continue
        for ref in re.findall(re.escape(BASIS_NAME) + r'\.(\w+)', formula):
            if ref not in jctx.basis.names:
                raise BuildError(f'{BASIS_NAME}.{ref} is not defined in {BASIS_NAME}.xml ({formula!r})')


def review_document(basis, sheets):
    """One document holding Basis (with the review banner), then the cap reports."""
    doc = bs.new_document()
    doc.append(copy.deepcopy(basis.review_rep))
    for sheet in sheets:
        doc.append(copy.deepcopy(sheet.rep))
    return bs.serialize(doc)


def write_journal_outputs(links, results, out_dir=None):
    """cap_bpad/journal/: fragments, sidecars, review document, coherence.json and verification.json. `results` are build tuples."""
    base = (OUT_DIR if out_dir is None else Path(out_dir)) / JOURNAL_SUBDIR
    (base / 'preview').mkdir(parents=True, exist_ok=True)
    basis = links.basis
    (base / f'{BASIS_NAME}.xml').write_bytes(basis.fragment)
    shown_base = f'cap_bpad/{JOURNAL_SUBDIR}' if out_dir is None else f'{Path(out_dir).name}/{JOURNAL_SUBDIR}'
    coherence, entries, sheets = {}, [], []
    for sheet, eng, meta, filename, ctx, cap in results:
        data = bs.serialize(sheet.rep, declaration=False).rstrip()
        (base / f'{sheet.name}.xml').write_bytes(data)
        sidecar = {name: cv.sidecar() for name, cv in sheet.canvases.items()}
        (base / 'preview' / f'{sheet.name}.canvases.json').write_text(json.dumps(sidecar, indent=1, ensure_ascii=False),
                                                                      encoding='utf-8', newline='\n')
        summary = meta['journal']
        coherence[sheet.name] = summary['rows']
        xml = ctx.e.case['analysis']['xml_audit']
        entries.append({
            'cap': cap['label'], 'report_file': ctx.report['file'], 'fragment': f'{shown_base}/{sheet.name}.xml', 'report_name': sheet.name,
            'case_sha256': ctx.report['case_sha'], 'formula_sha256': ctx.report['formula_sha'], 'fbmp_file': xml['filename'],
            'fbmp_sha256': xml['sha256'], 'package_revision': ctx.revision, 'stations': meta['stations'],
            'definitions': meta['definitions'], 'functions': meta['functions'], 'cells_and_labels': meta['cells'],
            'tool_comparisons': meta['comparisons'], 'sheet_comparisons': meta['shown'], 'coverage_comparisons': meta['coverage'],
            'coverage_rows_real': meta['coverage_real'], 'coverage_rows_synthetic': meta['coverage_synthetic'],
            'mathcad_values_compared': meta['mathcad_values'], 'branches_reached': meta['branches'], 'status': meta['status'],
            'journal_references': summary['references'], 'literals_kept': [r['input'] for r in summary['literals']],
            'references': sorted({r['owner'] for r in summary['rows'] if r['status'] == 'reference'}),
            'fragment_sha256': hashlib.sha256(data).hexdigest(),
        })
        sheets.append(sheet)
    review = review_document(basis, sheets)
    (base / REVIEW_FILE).write_bytes(review)
    write_json(base / 'coherence.json', coherence, sort_keys=False)       # rows keep the field order of the specification
    write_json(base / 'verification.json', {
        'journal_file': links.source, 'basis': {
            'report_name': BASIS_NAME, 'fragment': f'{shown_base}/{BASIS_NAME}.xml', 'fragment_sha256': hashlib.sha256(basis.fragment).hexdigest(),
            'constants': {name: clean(q.v) for name, q in basis.values.items()}, 'functions': sorted(basis.bars),
            'read_by': [e['report_name'] for e in entries]},
        'review_document': f'{shown_base}/{REVIEW_FILE}', 'review_sha256': hashlib.sha256(review).hexdigest(), 'reports': entries})
    return base


def write_json(path, value, sort_keys=True):
    Path(path).write_text(json.dumps(value, indent=1, ensure_ascii=False, sort_keys=sort_keys), encoding='utf-8', newline='\n')


def journal_line(name, summary):
    kept = summary['literals']
    text = f'{name}: {summary["references"]} journal references verified, {len(kept)} literal{"" if len(kept) == 1 else "s"} kept'
    if kept:
        units = summary['units']
        text += ' (' + '; '.join(f'{r["input"]}: journal {number_text(r["journal_value"])} {units[r["input"]]} vs '
                                 f'case {number_text(r["case_value"])} {units[r["input"]]}'.replace('  ', ' ') for r in kept) + ')'
    return text


def journal_path_from(argv):
    i = argv.index('--journal')
    if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
        path = Path(argv[i + 1])
        return path if path.is_absolute() or path.exists() else ROOT / path
    return JOURNAL_PATH


def main_journal(argv):
    compare_mathcad = '--skip-mathcad' not in argv
    links = bs.JournalLinks.load(journal_path_from(argv))
    results = []
    for cap in bm.CAPS:
        sheet, eng, meta, filename, ctx = build_cap(cap, compare_mathcad, journal=links)
        results.append((sheet, eng, meta, filename, ctx, cap))
        mine = f'; {meta["mathcad_values"]} match the Mathcad sheet' if compare_mathcad else ''
        print(f'{journal_line(sheet.name, meta["journal"])}; {meta["comparisons"]} values match the cap tool{mine}')
    base = write_journal_outputs(links, results)
    basis = links.basis
    print(f'{BASIS_NAME}: {len(basis.values)} shared factors, {len(basis.bars)} bar functions; read by '
          + ', '.join(r[0].name for r in results))
    print(f'Wrote {len(results) + 1} reports, {REVIEW_FILE}, coherence.json and verification.json to cap_bpad/{JOURNAL_SUBDIR}/')
    return 0


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    if '--journal' in argv:
        return main_journal(argv)
    compare_mathcad = '--skip-mathcad' not in argv
    entries = []
    for cap in bm.CAPS:
        sheet, eng, meta, filename, ctx = build_cap(cap, compare_mathcad)
        entry = write_outputs(sheet, eng, meta, filename, ctx, cap)
        entries.append(entry)
        mine = f'; {meta["mathcad_values"]} values match the Mathcad sheet' if compare_mathcad else ''
        print(f'Wrote cap_bpad/{filename}: {meta["definitions"]} definitions, {meta["functions"]} functions; '
              f'{meta["comparisons"]} values match the cap tool ({meta["coverage"]} from {meta["coverage_real"]} + '
              f'{meta["coverage_synthetic"]} branch-coverage rows){mine}; report {meta["report"]}')
    (OUT_DIR / 'verification.json').write_text(json.dumps(entries, indent=1, ensure_ascii=False, sort_keys=True), encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
