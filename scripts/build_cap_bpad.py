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
"""
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pier_cap.transverse import scheduled_bars  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402
from scripts import build_cap_mathcad as bm  # noqa: E402
from scripts import cap_mathcad_figures as figs  # noqa: E402
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
        return bs.bp_formula(tree, self.scal)

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
            text = text + ' ' + EXTRA_PROVENANCE
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
        formula = f'{name} = {self.formula_of(it.tree)}'
        caption = it.caption
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
            vals = vector_literal(it.tree)
            unit = 'in^2' if n == 'A_bar' else 'in'
            expr = f'0 {unit}'
            for k in range(len(vals) - 1, 2, -1):
                expr = f'If(k == {k}, {bs.bp_num(vals[k])} {unit}, {expr})'
            fname = 'Ab' if n == 'A_bar' else 'Db'
            self.eq(self.rep, f'{fname}(k) = {expr}', 'bar area by bar number' if n == 'A_bar' else 'bar diameter by bar number')
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
    env['A_bar'] = [to_u(eng.evaluate(f'Ab({k})')) for k in range(12)]
    env['d_bar'] = [to_u(eng.evaluate(f'Db({k})')) for k in range(12)]
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
def prepare(cap):
    e = bm.evaluate_cap(cap)
    rep = bm.report_link(cap, e)
    rev = bm.notebook_revision()
    rows = bm.governing_stations(e)
    bm.check_stations(e, rows)
    physical = scheduled_bars(e.case)
    dv, l_cap = e.value('dv', 'in'), e.value('L_cap', 'in')
    values = bm.station_values(e, rows, physical, dv, l_cap)
    ctx = SimpleNamespace(cap=cap, e=e, report=rep, revision=rev, values=bm.input_values(e), rows=rows,
                          spacing=bm.spacing_data(e), faces=bm.face_data(e), hook=bm.hook_data(e))
    blocks = bm.sheet_head(ctx) + bm.sheet_stations(ctx, rows, values) + bm.sheet_tail(ctx, ctx.spacing, ctx.faces, ctx.hook)
    return ctx, blocks, values, physical, dv, l_cap


def build_cap(cap, mathcad_compare=True):
    ctx, blocks, values, physical, dv, l_cap = prepare(cap)
    e = ctx.e
    report_name, title, filename = SIDE_BY_KEY[cap['key']]
    sheet = Sheet(cap, ctx, blocks, report_name, title)
    sheet.ctx_values = values
    for blk in blocks:
        getattr(sheet, 'do_' + blk.kind)(blk)
    sheet.flush()
    bs.note(sheet.rep, 'A distilled result of ✓ covers only the recomputed numerical checks; it is not design acceptance. Recalculate in Blockpad after any input change.', size=9)

    rep = sheet.rep
    # ---- (a) syntax and names: the engine is built from the XML that will be written
    eng = bs.BpEngine(report=report_name)
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
    return sheet, eng, meta, filename, ctx


def coverage_comparisons(sheet, eng, ctx, cover, cover_rows, cover_values):
    """Station equations for the branch-coverage rows, evaluated by a throwaway engine next to the head definitions."""
    n = len(cover_rows)
    cov = bs.BpEngine(report=sheet.name)
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


def write_outputs(sheet, eng, meta, filename, ctx, cap):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / 'fragments').mkdir(exist_ok=True)
    (OUT_DIR / 'preview').mkdir(exist_ok=True)
    data = bs.serialize(sheet.doc)
    (OUT_DIR / filename).write_bytes(data)
    (OUT_DIR / 'fragments' / f'{sheet.name}.xml').write_bytes(bs.serialize(sheet.rep, declaration=False).rstrip())
    sidecar = {name: cv.sidecar() for name, cv in sheet.canvases.items()}
    (OUT_DIR / 'preview' / f'{sheet.name}.canvases.json').write_text(json.dumps(sidecar, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
    xml = ctx.e.case['analysis']['xml_audit']
    return {
        'cap': cap['label'], 'report_file': ctx.report['file'], 'bpad_file': f'cap_bpad/{filename}', 'report_name': sheet.name,
        'case_sha256': ctx.report['case_sha'], 'formula_sha256': ctx.report['formula_sha'], 'fbmp_file': xml['filename'],
        'fbmp_sha256': xml['sha256'], 'package_revision': ctx.revision, 'stations': meta['stations'],
        'definitions': meta['definitions'], 'functions': meta['functions'], 'cells_and_labels': meta['cells'],
        'tool_comparisons': meta['comparisons'], 'sheet_comparisons': meta['shown'], 'coverage_comparisons': meta['coverage'],
        'coverage_rows_real': meta['coverage_real'], 'coverage_rows_synthetic': meta['coverage_synthetic'],
        'mathcad_values_compared': meta['mathcad_values'], 'branches_reached': meta['branches'], 'status': meta['status'],
        'bpad_sha256': hashlib.sha256(data).hexdigest(),
    }


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
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
