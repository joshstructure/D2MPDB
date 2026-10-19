"""Build the Blockpad (.bpad) edition of the distilled end-bent backwall worksheet.

The Mathcad generator (scripts/build_backwall_mathcad.py) holds the equation list. This script walks the same blocks
(`build_backwall_mathcad.sheet(rev)`), translates each equation to Blockpad syntax (scripts/bpad_sheet.py) and writes one
standalone document with one report, `EndBentBackwallDesign`. Blockpad has no vector variables, so the five load
combinations, the three members (backwall fill face, backwall span face, cheek wall) and the eight torsion stations
become scalars; each equation is shown once (Service I, fill face, station 0, Strength I) and the others sit in collapsed
sections, with their values side by side in green tables. The figures are native canvases.

Before anything is written, every definition is evaluated by the independent Blockpad-syntax evaluator (BpEngine) and
compared with the notebook model (build_backwall_mathcad.comparisons) and, for the registered case, with the verified
Mathcad environment. The build stops on any mismatch.

    python scripts/build_backwall_bpad.py                  # write end_bent_walls/End Bent Backwall Design.bpad + bpad/
    python scripts/build_backwall_bpad.py --skip-mathcad   # skip the comparison with the Mathcad environment
    python scripts/build_backwall_bpad.py --journal [path] # journal edition into end_bent_walls/bpad/journal/ (live references)

The journal edition writes the same report with the inputs the journal owns (end-bent cap, backwall and cheek dimensions, bearing
pad data and the Span 1 expansion length from BridgeGeometry_2Beam; the material strengths from Materials) as live references,
the project stamp as live ProjectInfo cells, and a reference to BridgeGeometry_2Beam.EndBent_backwallDrop beside the measured
backwall heights. A coherence gate compares every referenced journal value with the notebook input before anything is built
(JOURNAL_REFS, KEEP_LITERAL and `journal_context` below; see cap_bpad/README.md, "Journal edition"). The strap loads, the
bearing actions and everything else stay as the case holds them.
"""
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from end_bent_walls.model import COMBINATIONS, INPUTS as INPUT_SPEC, evaluate  # noqa: E402
from scripts import bpad_sheet as bs  # noqa: E402
from scripts import build_backwall_mathcad as bm  # noqa: E402
from scripts import mathcad_sheet as ms  # noqa: E402
from scripts.mathcad_sheet import U  # noqa: E402

REPORT_NAME = 'EndBentBackwallDesign'
TITLE = 'End Bent 1 Backwall, Cheek Walls and Tie-Back Straps - Distilled'
FILENAME = 'End Bent Backwall Design.bpad'
OUT_DIR = ROOT / 'end_bent_walls'
SIDE_DIR = OUT_DIR / 'bpad'
EXTRA_PROVENANCE = ('Blockpad edition written by scripts/build_backwall_bpad.py from the same case; every definition was '
                    'evaluated independently and compared with the notebook to 1 part in 10⁹.')
NOTEBOOK_PROVENANCE = ('Blockpad edition exported from the backwall notebook (scripts/build_backwall_bpad.py in memory) for this '
                       'case; every definition was evaluated independently and compared with the notebook to 1 part in 10⁹.')
CLOSING_NOTE = ('A distilled result of ✓ covers only the recomputed numerical checks; it is not design acceptance. '
                'Recalculate in Blockpad after any input change.')
TOL = 1e-9                                           # comparison with the notebook and the Mathcad environment
INPUT_TOL = 1e-12
PAGE_BREAK_BEFORE = {3, 6, 9, 12}
PASS_TEXT, FAIL_TEXT = '✓ PASS', '⊗ FAIL'
ALL_PASS, FAILURES = '✓ All Checks Pass', '⊗ There are FAILURES'

# ----------------------------------------------------------------------------- families
KEYS = [c['key'] for c in COMBINATIONS]                          # SERI STRI STRIII1 STRIII2 STRIV
COMBO_LABELS = [c['label'] for c in COMBINATIONS]
MEMBERS = ['FF', 'SF', 'CK']
MEMBER_LABELS = ['Backwall fill face', 'Backwall span face', 'Cheek wall']
STATIONS = [str(k) for k in range(8)]
R_KEYS = KEYS[1:]                                                # the four strength combinations (r = 1..4)
FAMILY_TAGS = {'i': KEYS, 'j': MEMBERS, 'k': STATIONS, 'r': R_KEYS}
FAMILY_TAGS['kr'] = [f'{k}_{r}' for k in STATIONS for r in R_KEYS]
RANGEVARS = ('i', 'j', 'k', 'r')
LITERAL_LENGTH_FAMILY = {5: 'i', 3: 'j', 8: 'k'}
FN_NAMES = {'L_core', 'L_w', 'N_b', 'N_c'} | {f'T_c_{r}' for r in R_KEYS}
VEC_GREEK = {'phi': 'φ', 'rho': 'ρ'}
# display units of definitions the Mathcad sheet leaves without one
D_UNITS = {'H_W': 'kip', 'FZ_W': 'kip', 'h_w': 'in', 'c_v': 'in', 's_w': 'in', 's_max': 'in', 'X_T': 'ft',
           't_u': 'kip*ft/ft', 't_cap': 'kip*ft/ft', 't_b': 'kip*ft/ft', 'P_b': 'kip*ft', 'P_c': 'kip*ft'}
UNIT_OVERRIDE = {'T_A': 'kip*ft', 'T_B': 'kip*ft'}
MEMBER_CHECKS = ['DC_flex', 'DC_min', 'DC_eps', 'DC_crk', 'DC_sp']
SINGLE_CHECKS = ['DC_V_bw', 'DC_Vi_bw', 'DC_Avf', 'DC_ts_v', 'DC_ts_h', 'DC_V_ck', 'DC_Vi_ck', 'DC_ts_ck', 'DC_cov', 'DC_thk',
                 'DC_strap', 'DC_T']
CHECK_SCOPE = {'DC_V_bw': 'Backwall', 'DC_Vi_bw': 'Backwall', 'DC_Avf': 'Backwall', 'DC_ts_v': 'Backwall',
               'DC_ts_h': 'Backwall', 'DC_V_ck': 'Cheek wall', 'DC_Vi_ck': 'Cheek wall', 'DC_ts_ck': 'Cheek wall',
               'DC_cov': 'Backwall and cheek wall', 'DC_thk': 'Backwall and cheek wall', 'DC_strap': 'Backwall',
               'DC_T': 'Cap'}
SECTION_NOTE = {
    'i': 'The other four combinations (Strength I, Strength III wind 1, Strength III wind 2, Strength IV): the same equations, collapsed.',
    'j': 'Backwall span face (SF) and cheek wall (CK): the same equations, collapsed.',
    'k': 'Stations 1 to 7: the same equations, collapsed.',
}
FAMILY_NAME = {'i': 'Combos', 'j': 'Members', 'k': 'Stations'}
PLAIN_TEXT = {
    'Vectors hold': ('Each quantity below is written for the five combinations in this order: Service I, Strength I, Strength III '
                     'wind 1, Strength III wind 2, Strength IV (LRFD Tables 3.4.1-1 and 3.4.1-2). TU and SH share one factor. Wind '
                     'takes γWS = 1.0 where it applies; vertical wind counts only when it increases overturning. Blockpad has no '
                     'vector variables: the equations are shown for Service I, the other combinations repeat them in the '
                     'collapsed sections, and the values of all five appear side by side in the green tables.'),
    'Index j:': ('Members: FF = backwall fill face (strap slack), SF = backwall span face (strap engaged), CK = cheek wall (either '
                 'face). The equations are shown for the fill face; the span face and the cheek wall repeat them in the collapsed '
                 'sections and the green tables.'),
}
FIG1_HEIGHT = 5.6
FIG1_KEY = ('Key: F_EH, F_ES and F_LS are the earth, slab and pedestrian surcharge resultants; F_str is the tie-back strap force; '
            'F_TU, F_SH and H_WS are the pad shear and the longitudinal wind; W_DCb and W_PLb are the superstructure and pedestrian '
            'loads; W_cap, W_ped, W_bw and W_ck are the self-weights. The blue dimensions are the arms x from the shifted pile line '
            'and the heights y above O; their values are live.')
K_R_NOTE = ('Stations k = 0 to 7 are X_T_0 to X_T_7; combinations r are the four strength combinations (Strength I, Strength III '
            'wind 1, Strength III wind 2, Strength IV). The equations are shown for station 0 and Strength I; the other 62 values '
            'sit in the collapsed section and the green table lists the larger of T_A and T_B at each station.')


class BuildError(AssertionError):
    pass


def vname(base):
    """Blockpad name stem of a vector quantity."""
    if base in VEC_GREEK:
        return VEC_GREEK[base]
    if base.startswith('gamma_'):
        return 'γ_' + base[len('gamma_'):]
    return bs.bp_name(base)


def to_u(q):
    """Mathcad-environment value of a Blockpad quantity (angles are plain radians there)."""
    if isinstance(q, bs.Q):
        return U(q.v, (q.d[0], q.d[1]))
    return q


def clean(v):
    return float(f'{v:.12g}')


def literal_numbers(tree):
    """The numbers of a tr(row(...)) literal made only of plain numbers, else None."""
    elems = row_elements(tree)
    if elems is None:
        return None
    out = []
    for a in elems:
        if a[0] == 'num':
            out.append(a[1])
        elif a[0] == 'neg' and a[1][0] == 'num':
            out.append(-a[1][1])
        else:
            return None
    return out


def row_elements(tree):
    """The element trees of tr(row(...)) / row(...) / col(...), else None."""
    if tree[0] == 'call' and tree[1] == 'tr':
        return row_elements(tree[2][0])
    if tree[0] == 'call' and tree[1] in ('row', 'col'):
        return list(tree[2])
    return None


def vector_literal(tree):
    """The numbers of the first row()/col() literal inside a parse tree (for the bar tables)."""
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


def arrow(cv, x1, y1, x2, y2, color, width=1.4, head=0.1):
    """A line with a two-stroke arrowhead at (x2, y2)."""
    cv.line([(x1, y1), (x2, y2)], color, width)
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1e-6:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    hl, th = min(head, length * 0.6), 0.45
    pts = []
    for sign in (1, -1):
        c, s = math.cos(sign * th), math.sin(sign * th)
        pts.append((x2 + hl * (-ux * c + uy * s), y2 + hl * (-ux * s - uy * c)))
    cv.line([pts[0], (x2, y2), pts[1]], color, width)


def arc(cv, cx, cy, r, a0, a1, color, width=1.2):
    """A circular arrow from angle a0 to a1 (degrees, counterclockwise positive) with an arrowhead at the end."""
    n = 14
    pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
           for i in range(n + 1)]
    cv.line(pts, color, width)
    sign = 1 if a1 > a0 else -1
    tx, ty = -math.sin(math.radians(a1)) * sign, math.cos(math.radians(a1)) * sign
    arrow(cv, pts[-1][0] - tx * 0.08, pts[-1][1] - ty * 0.08, pts[-1][0] + tx * 0.02, pts[-1][1] + ty * 0.02, color, width, 0.09)


# ----------------------------------------------------------------------------- the sheet
class Sheet:
    """The report: walks the Mathcad blocks and writes the native elements."""

    def __init__(self, e, blocks, revision, extra_provenance):
        self.e, self.blocks, self.revision = e, blocks, revision
        self.extra_provenance = extra_provenance
        self.name = REPORT_NAME
        self.doc = bs.new_document()
        self.rep = bs.new_report(self.doc, REPORT_NAME, TITLE)
        self.case_sha = hashlib.sha256(json.dumps(e.case, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.family, self.vector_map, self.scalar_map = {}, {}, {}
        self.cur = {'i': KEYS[0], 'j': MEMBERS[0], 'k': STATIONS[0], 'r': R_KEYS[0]}
        self.pending = []
        self.captions = {}
        self.sec = 0
        self.groups = 0
        self.deferred, self.canvases = [], {}
        self.chart_names = []
        self.input_names = []
        self.gamma_done = False
        self.journal = None                                  # JournalContext in the journal edition
        # pre-scan: the S(tr(NAME)) display items, and the literal factor vectors
        self.shows = {}
        self.literals = []
        for blk in blocks:
            if blk.kind not in ('eqs', 'row'):
                continue
            for it in blk.payload:
                if it.kind == 'show':
                    m = re.fullmatch(r'tr\((\w+)\)', it.expr or '')
                    if m and m.group(1) not in ('Combo', 'Member'):
                        self.shows[m.group(1)] = it
                elif it.kind == 'def' and it.name not in ('Combo', 'Member', 'A_bar', 'd_bar'):
                    nums = literal_numbers(it.tree)
                    if nums is not None:
                        self.literals.append((it, nums))

    # -- scalar naming
    @staticmethod
    def tags_of(fam):
        return FAMILY_TAGS[fam]

    def register(self, name, fam):
        self.family[name] = fam
        self.vector_map[name] = [self.sname(name, t) for t in self.tags_of(fam)]

    def sname(self, base, tag):
        return f'{vname(base)}_{tag}'

    def scal(self, base, idx):
        fam = self.family.get(base)
        if fam is None:
            return None
        if idx is None:
            return list(self.vector_map[base])
        if isinstance(idx, str):
            if fam == 'kr':
                raise BuildError(f'{base}: a two-index quantity indexed by {idx} alone')
            return self.sname(base, self.cur[idx])
        return self.sname(base, self.tags_of(fam)[idx])

    def set_cur(self, fam, tag):
        if fam == 'kr':
            k, r = tag.split('_', 1)
            self.cur['k'], self.cur['r'] = k, r
        else:
            self.cur[fam] = tag

    # -- trees to Blockpad text
    def rewrite(self, t, fam):
        """The tree with bare vectors indexed by the family's range variable, range variables as numbers, T_c calls split by
        combination and IF conditions on two numbers folded."""
        k = t[0]
        if k == 'id':
            v = t[1]
            if v in self.family and v not in ms.UNITS:
                if fam in ('i', 'j', 'k') and self.family[v] == fam:
                    return ('idx', t, [('id', fam)])
                if fam is None or self.family[v] != fam:
                    return t                                 # flattened by max()/min(), or an error in the emitter
            if v in RANGEVARS and v not in self.family:
                return ('num', float(FAMILY_TAGS[v].index(self.cur[v])))
            return t
        if k in ('num', 'str'):
            return t
        if k == 'neg':
            return ('neg', self.rewrite(t[1], fam))
        if k == 'bin':
            return ('bin', t[1], self.rewrite(t[2], fam), self.rewrite(t[3], fam))
        if k == 'cmp':
            return ('cmp', t[1], self.rewrite(t[2], fam), self.rewrite(t[3], fam))
        if k in ('and', 'or'):
            return (k, self.rewrite(t[1], fam), self.rewrite(t[2], fam))
        if k == 'idx':
            index = [i if (i[0] == 'id' and i[1] in RANGEVARS) else self.rewrite(i, fam) for i in t[2]]
            return ('idx', t[1], index)
        if k == 'call':
            f, args = t[1], t[2]
            if f == 'T_c':
                if len(args) != 2 or args[1] != ('id', 'r'):
                    raise BuildError('T_c is called as T_c(x, r)')
                return ('call', f'T_c_{self.cur["r"]}', [self.rewrite(args[0], fam)])
            args = [self.rewrite(a, fam) for a in args]
            if f == 'IF' and args[0][0] == 'cmp' and args[0][2][0] == 'num' and args[0][3][0] == 'num':
                a, b = args[0][2][1], args[0][3][1]
                holds = {'>': a > b, '<': a < b, '>=': a >= b, '<=': a <= b, '==': a == b}[args[0][1]]
                return args[1] if holds else args[2]
            return ('call', f, args)
        raise BuildError(f'unhandled tree {k}')

    def formula_of(self, tree, fam=None):
        return bs.bp_formula(self.rewrite(tree, fam), self.scal, functions=FN_NAMES)

    def item_formula(self, name, tree, unit, fam=None):
        text = f'{name} = {self.formula_of(tree, fam)}'
        u = bs.bp_unit(unit)
        return text + (f' to {u}' if u else '')

    def eq(self, parent, formula, caption='', style=None, show_result=True, inline=False):
        return bs.equation(parent, formula, caption, style=style, show_result=show_result, inline=inline)

    # -- plain blocks
    def do_title(self, blk):
        if self.journal is not None:                         # the journal edition opens with the live project stamp
            bs.project_stamp_table(self.rep, self.journal.stamp, live=True)
        bs.para(self.rep, 'D2 I-95 PEDESTRIAN BRIDGE', fontsize=16, fontweight='bold', spacingafter=2)
        bs.para(self.rep, blk.payload, fontsize=14, fontweight='bold', spacingafter=6)

    def do_h1(self, blk):
        self.sec = int(blk.payload.split('.')[0])
        bs.heading(self.rep, blk.payload, page_break=self.sec in PAGE_BREAK_BEFORE)
        if self.journal is not None and self.sec == 2:
            bs.note(self.rep, JOURNAL_SECTION2)

    def do_h2(self, blk):
        bs.subheading(self.rep, blk.payload)

    def do_p(self, blk):
        text = blk.payload
        if text.startswith('Mathcad edition of'):
            text = (f'Blockpad edition of End_Bent_Backwall_Design.ipynb (calculation package {self.revision}; case SHA-256 '
                    f'{self.case_sha}). Same inputs, equations and load combinations as the notebook; every result below was '
                    f'recomputed and compared with the notebook. ' + self.extra_provenance)
        elif text.startswith('Status:'):
            text = text.replace('Inputs are highlighted yellow; values for the plans are boxed.',
                                'Inputs are highlighted amber; distilled results are the green tables.')
        elif text.startswith('Demand / capacity ratios'):
            text = text.replace('Rows j as in Section 9.', 'Members FF, SF and CK as in Section 9.')
        else:
            for start, replacement in PLAIN_TEXT.items():
                if text.startswith(start):
                    text = replacement
                    break
        bs.para(self.rep, text)

    def do_note(self, blk):
        bs.note(self.rep, blk.payload)

    def do_bullets(self, blk):
        for item in blk.payload:
            bs.para(self.rep, '• ' + item, spacingafter=4)

    def do_fig(self, blk):
        fig1 = blk.payload == 'section'
        name = 'Figure1Section' if fig1 else 'Figure2Strip'
        cv = bs.canvas(self.rep, name, 'End-bent section' if fig1 else 'Backwall strip', FIG1_HEIGHT if fig1 else 4.0)
        self.canvases[name] = cv
        self.deferred.append((cv, (lambda eng, cv=cv, f1=fig1: self.draw_section(cv, eng) if f1 else self.draw_strip(cv, eng))))
        bs.note(self.rep, blk.opts['caption'])
        if fig1:
            bs.note(self.rep, FIG1_KEY)

    # -- inputs
    def do_inputs(self, blk):
        bs.para(self.rep, blk.opts['title'], fontweight='bold', spacingbefore='4', spacingafter='3', keepwithnext='True')
        for it in blk.payload:
            self.input_item(it)
        if self.journal is not None and blk.opts['title'].startswith('Geometry'):
            owner, unit = self.journal.drop
            self.eq(self.rep, f'{DROP_NAME} = {owner} to {unit}', self.journal.drop_caption)

    def input_item(self, it):
        spec = INPUT_SPEC[it.name]
        unit = None if spec['unit'] in (None, 'bar') else bs.bp_unit(spec['unit'])
        value = self.e.case['inputs'][it.name]
        name = bs.bp_name(it.name)
        self.scalar_map[it.name] = name
        self.input_names.append(it.name)
        if self.journal is not None and it.name in self.journal.refs:      # journal edition: a live reference, not a literal
            owner, ref_unit = self.journal.refs[it.name]
            self.eq(self.rep, f'{name} = {owner}' + (f' to {ref_unit}' if ref_unit else ''), f'{REFERENCE_CAPTION} {owner}')
            return
        formula = f'{name} = {bs.bp_num(value)}' + (f' {unit}' if unit else '')
        caption = it.caption
        if self.journal is not None and it.name in self.journal.keep:
            caption = self.journal.keep[it.name]['reason']
        self.eq(self.rep, formula, caption, style='Required Input', show_result=False, inline=bool(caption) and len(caption) <= 45)

    # -- equations
    def do_eqs(self, blk):
        items = blk.payload
        if items and all(it.kind == 'show' for it in items):
            return self.plan_table(items)
        for it in items:
            self.item(it)
        self.flush()

    def do_row(self, blk):
        items = blk.payload
        if [it.name for it in items if it.kind == 'range'] == ['k', 'r']:
            bs.note(self.rep, K_R_NOTE)
        for it in items:
            self.item(it)

    def item(self, it):
        k = it.kind
        if k in ('range', 'show'):
            return
        if k == 'eq':
            return self.do_E(it)
        if k == 'def':
            return self.do_D(it)
        if k == 'idef':
            return self.do_V(it)
        if k == 'fdef':
            return self.do_F(it)
        raise BuildError(f'unhandled item {k} {it.name}')

    def do_E(self, it):
        self.flush()
        if it.name == 'Status':
            return self.summary()
        name = bs.bp_name(it.name)
        self.scalar_map[it.name] = name
        self.captions[it.name] = it.caption
        self.eq(self.rep, self.item_formula(name, it.tree, it.unit), it.caption)

    def do_F(self, it):
        params = ', '.join(it.params)
        if it.name == 'T_c':
            if it.params != ['x', 'r']:
                raise BuildError('T_c takes (x, r)')
            for r, label in zip(R_KEYS, COMBO_LABELS[1:]):
                self.cur['r'] = r
                self.eq(self.rep, f'T_c_{r}(x) = {self.formula_of(it.tree)}', f'{it.caption}; {label}')
            return
        self.eq(self.rep, f'{bs.bp_name(it.name)}({params}) = {self.formula_of(it.tree)}', it.caption)

    def vector_unit(self, name, unit):
        shown = self.shows.get(name)
        return (shown.unit if shown is not None and shown.unit else None) or unit or D_UNITS.get(name) or UNIT_OVERRIDE.get(name)

    def do_D(self, it):
        n = it.name
        if n in ('A_bar', 'd_bar'):
            _, formula, caption = bar_function(it)
            self.eq(self.rep, formula, caption)
            return
        if n in ('Combo', 'Member'):
            return
        if n in ('M_u', 'M_s'):                         # aliases of the scalars M_u_FF, ... defined in Section 6
            self.register(n, 'j')
            return
        if any(it is lit for lit, _ in self.literals):
            return self.gamma_table()
        elems = row_elements(it.tree)
        if elems is not None:
            fam = LITERAL_LENGTH_FAMILY.get(len(elems))
            if fam is None:
                raise BuildError(f'{n}: a literal vector of {len(elems)} elements')
            trees = elems
        else:
            fams = {self.family[v] for v in ms.names_in(it.tree) if v in self.family}
            if len(fams) != 1:
                raise BuildError(f'{n}: cannot tell the family of an implicit vector ({sorted(fams)})')
            fam = fams.pop()
            trees = None
        self.register(n, fam)
        shown = self.shows.get(n)
        caption = (shown.caption if shown is not None and shown.caption else '') or it.caption
        self.captions[n] = caption
        unit = self.vector_unit(n, None)
        formulas = {}
        for pos, tag in enumerate(self.tags_of(fam)):
            self.set_cur(fam, tag)
            tree = trees[pos] if trees is not None else it.tree
            formulas[tag] = self.item_formula(self.sname(n, tag), tree, unit, fam)
        self.add_pending(n, fam, caption, unit, shown is not None, formulas)

    def do_V(self, it):
        fam = 'kr' if isinstance(it.index, tuple) else it.index
        if fam not in ('i', 'j', 'kr'):
            raise BuildError(f'unhandled range {it.index} for {it.name}')
        self.register(it.name, fam)
        self.captions[it.name] = it.caption
        unit = it.unit or UNIT_OVERRIDE.get(it.name)
        formulas = {}
        for tag in self.tags_of(fam):
            self.set_cur(fam, tag)
            formulas[tag] = self.item_formula(self.sname(it.name, tag), it.tree, unit, fam if fam != 'kr' else None)
        self.add_pending(it.name, fam, it.caption, unit, it.show, formulas)

    def add_pending(self, name, fam, caption, unit, show, formulas):
        first = self.tags_of(fam)[0]
        self.eq(self.rep, formulas[first], caption, show_result=show)
        self.pending.append(dict(name=name, fam=fam, caption=caption, unit=bs.bp_unit(unit), show=show, formulas=formulas))

    # -- hidden sections and green tables
    def flush(self):
        """The other combinations / members / stations collected since the last flush (collapsed) and their tables."""
        if not self.pending:
            return
        self.groups += 1
        n = self.groups
        for fam in ('i', 'j', 'k', 'kr'):
            items = [p for p in self.pending if p['fam'] == fam]
            if not items:
                continue
            tags = self.tags_of(fam)
            if fam == 'kr':
                self.flush_torsion(items, n)
                continue
            bs.note(self.rep, SECTION_NOTE[fam])
            sec = bs.section(self.rep, f'Rest_{FAMILY_NAME[fam]}_{n}')
            for tag in tags[1:]:
                for p in items:
                    self.eq(sec, p['formulas'][tag], show_result=p['show'])
            heads = {'i': COMBO_LABELS, 'j': MEMBER_LABELS, 'k': [f'k = {t}' for t in STATIONS]}[fam]
            widths = {'i': [230] + [90] * 5, 'j': [270] + [130] * 3, 'k': [150] + [58] * 8}[fam]
            rows = []
            for p in items:
                stem = vname(p['name'])
                label = (f'{stem}: {p["caption"]}' if p['caption'] else stem) + (f' ({p["unit"]})' if p['unit'] else '')
                rows.append([label] + [('formula', self.sname(p['name'], t) + (f' to {p["unit"]}' if p['unit'] else '')) for t in tags])
            bs.table(self.rep, f'Table_{FAMILY_NAME[fam]}_{n}', ['Quantity'] + heads, rows, widths, 'output',
                     font='9' if fam == 'k' else '10')
        self.pending = []

    def flush_torsion(self, items, n):
        bs.note(self.rep, 'The other 62 station and combination values of T_A and T_B: the same equations, collapsed.')
        sec = bs.section(self.rep, f'Rest_Torque_{n}')
        first = self.tags_of('kr')[0]
        for p in items:
            for tag in self.tags_of('kr'):
                if tag != first:
                    self.eq(sec, p['formulas'][tag], show_result=p['show'])
        by = {p['name']: p for p in items}
        rows = []
        for k in STATIONS:
            cells = [f'k = {k}', ('formula', f'X_T_{k} to ft')]
            for r in R_KEYS:
                a, b = self.sname('T_A', f'{k}_{r}'), self.sname('T_B', f'{k}_{r}')
                cells.append(('formula', f'Max({a}, {b}) to kip*ft'))
            rows.append(cells)
        if set(by) != {'T_A', 'T_B'}:
            raise BuildError('the torsion group is not T_A and T_B')
        bs.note(self.rep, 'Larger of the torque at each station and just before it, by strength combination (kip*ft).')
        bs.table(self.rep, f'Table_Torque_{n}', ['Station', 'X_T (ft)'] + COMBO_LABELS[1:], rows, [90, 90, 120, 120, 120, 120], 'output')

    def gamma_table(self):
        if self.gamma_done:
            return
        self.gamma_done = True
        bs.para(self.rep, 'Load factors γ for the five combinations', fontweight='bold', spacingbefore='4', spacingafter='3',
                keepwithnext='True')
        rows = []
        for it, nums in self.literals:
            if len(nums) != len(KEYS):
                raise BuildError(f'{it.name}: {len(nums)} factors for {len(KEYS)} combinations')
            self.register(it.name, 'i')
            rows.append([vname(it.name)] + [('define', f'{self.sname(it.name, tag)} = {bs.bp_num(v)}', 'Required Input')
                                           for tag, v in zip(KEYS, nums)])
        bs.table(self.rep, 'GammaFactors', ['Factor'] + COMBO_LABELS, rows, [110] + [100] * 5, 'input')

    def plan_table(self, items):
        rows = []
        for it in items:
            if it.tree[0] != 'id':
                raise BuildError(f'unhandled shown expression {it.expr}')
            unit = bs.bp_unit(it.unit)
            rows.append([f'{it.caption}, {bs.bp_name(it.expr)}' + (f' ({unit})' if unit else ''),
                         ('formula', bs.bp_name(it.expr) + (f' to {unit}' if unit else ''))])
        bs.table(self.rep, 'PlanLoads', ['Tie-back load', 'Value'], rows, [420, 120], 'output')

    # -- summary
    def expanded_checks(self):
        """(ratio name, Chk name, text, scope) of every check of Section 12, with the members expanded."""
        out = []
        for base in MEMBER_CHECKS:
            for m, label in zip(MEMBERS, MEMBER_LABELS):
                out.append((f'{base}_{m}', f'Chk_{base[3:]}_{m}', self.captions[base], label))
        for name in SINGLE_CHECKS:
            out.append((name, 'Chk_' + name[3:], self.captions[name], CHECK_SCOPE[name]))
        return out

    def summary(self):
        self.eq(self.rep, f'Status = If(DC_max <= 1, "{ALL_PASS}", "{FAILURES}")', 'all numerical checks', style='Result only')
        checks = self.expanded_checks()
        sec = bs.section(self.rep, 'Checks')
        for dc, chk, _, _ in checks:
            self.eq(sec, f'{chk} = If({dc} <= 1, "{PASS_TEXT}", "{FAIL_TEXT}")')
        rows = [[f'{i}. {text}', where, ('formula', dc), ('formula', chk)] for i, (dc, chk, text, where) in enumerate(checks, 1)]
        rows.append(['OVERALL', 'all checks', ('formula', 'DC_max'), ('formula', 'Status')])
        bs.table(self.rep, 'Summary', ['Check', 'Member / scope', 'D/C', 'Result'], rows, [270, 170, 70, 120], 'output')
        names = [dc for dc, _, _, _ in checks]
        self.chart_names = names
        self.eq(self.rep, 'DC_ymax = Max(1.2, 1.1*Max(' + ', '.join(names) + '))', 'vertical scale of Figure 3')
        cv = bs.canvas(self.rep, 'DCChart', 'D/C by check', 3.2)
        self.canvases['DCChart'] = cv
        self.deferred.append((cv, lambda eng, cv=cv: self.draw_chart(cv, eng)))
        bs.note(self.rep, 'Figure 3. Demand/capacity ratio of each distilled check (stems, numbered as in the Summary table) against '
                          'the 1.0 limit. The stems are live formulas of the check ratios: a stem turns red when its ratio passes 1.0.')

    # -- figures
    def draw_section(self, cv, eng):
        """Figure 1: end-bent section with the loads, the arms from the shifted pile line O and the heights above O."""
        from end_bent_walls.schematics import _geometry
        e = self.e
        R = self.name
        g = _geometry(e)
        tol, b, h, tb, H = g['tol'], g['b'], g['h'], g['tb'], g['H']
        rear, front, emb, hped, tpad, lpad = g['rear'], g['front'], g['emb'], g['hped'], g['tpad'], g['lpad']
        ebrg, dp, zs, ts, Hck, wck, pad_top = g['ebrg'], g['dp'], g['zs'], g['ts'], g['Hck'], g['wck'], g['pad_top']
        top = h + max(H + ts, Hck)
        xmin, xmax, ymin, ytop = rear - 4.1, front + 2.6, -2.8, top + 0.5
        s = min(5.0 / (ytop - ymin), 5.9 / (xmax - xmin))
        x_off = (6.5 - (xmax - xmin) * s) / 2
        X = lambda x: x_off + (x - xmin) * s
        Y = lambda y: 0.2 + (y - ymin) * s
        shown = lambda name: eng.display(name)
        LOAD, GRAV, DIM, STRAP = bs.ROSE, bs.ORANGE, bs.BLUE, bs.TEAL
        cv.label(0.15, FIG1_HEIGHT - 0.25, 'END-BENT SECTION: LOADS, ARMS AND HEIGHTS', color=bs.INK, size=9, bold=True)
        # fill, slab, concrete
        cv.rect(X(rear - 4.1), Y(0), X(rear), Y(h + H), bs.GREY, 0.9)
        cv.label(X(rear - 3.3), Y((h + H) * 0.85), 'MSE fill', color=bs.GREY, size=8)
        cv.rect(X(rear - 4.1), Y(h + H), X(rear + tb), Y(h + H + ts), bs.GREY, 1.0)
        cv.label(X(rear - 3.95), Y(h + H + ts) + 0.04, 'landing slab', color=bs.GREY, size=8)
        cv.rect(X(ebrg - 0.4), Y(pad_top), X(xmax - 0.05), Y(top + 0.3), bs.GREY, 0.7)
        cv.label(X(front + 1.55), Y(top + 0.3) - 0.14, 'beam', color=bs.GREY, size=8)
        cv.rect(X(rear), Y(h), X(rear + wck), Y(h + Hck), bs.GREY, 0.6)
        cv.label(X(rear) - 1.1, Y(h + Hck) - 0.1, 'cheek wall (behind)', color=bs.GREY, size=8)
        cv.rect(X(-dp / 2), Y(-2.0), X(dp / 2), Y(emb), bs.GREY, 0.9)
        cv.rect(X(rear), Y(0), X(front), Y(h), bs.INK, 1.8)
        cv.rect(X(rear), Y(h), X(rear + tb), Y(h + H), bs.INK, 1.8)
        cv.rect(X(rear + tb), Y(h), X(front), Y(h + hped), bs.INK, 1.0)
        cv.rect(X(ebrg - lpad / 2), Y(h + hped), X(ebrg + lpad / 2), Y(pad_top), bs.INK, 1.6)
        cv.label(X(rear + 0.15), Y(h * 0.18), 'cap', color=bs.GREY, size=8)
        cv.label(X(rear + 0.08), Y(h + H * 0.9), 'backwall', color=bs.GREY, size=8)
        # pile lines and O
        cv.line([(X(xmin), Y(emb)), (X(xmax), Y(emb))], bs.GREY, 0.7)
        cv.label(X(xmax) - 0.55, Y(emb) + 0.04, 'pile top', color=bs.GREY, size=8)
        cv.line([(X(-tol), Y(-2.65)), (X(-tol), Y(h + 0.1))], DIM, 0.9)
        cv.line([(X(0), Y(-2.65)), (X(0), Y(-0.05))], bs.GREY, 0.7)
        cv.circle(X(-tol), Y(emb), 0.06, '#FFFFFF', DIM, 1.4)
        cv.label(X(-tol) - 0.2, Y(emb) - 0.14, 'O', color=DIM, size=9, bold=True)
        cv.label(X(-tol) - 1.0, Y(-2.78), 'shifted pile line', color=DIM, size=8)
        cv.label(X(0) + 0.06, Y(-2.78), 'pile', color=bs.GREY, size=8)
        # horizontal loads
        y_eh, y_es = (h + H) / 3, (h + H) / 2
        for y, label in ((y_eh, 'F_EH'), (y_es, 'F_ES, F_LS')):
            arrow(cv, X(rear - 1.35), Y(y), X(rear) - 0.01, Y(y), LOAD, 1.6)
            cv.label(X(rear - 1.35), Y(y) + 0.05, label, color=LOAD, size=8, bold=True)
        y_s = h + zs
        arrow(cv, X(rear), Y(y_s), X(rear - 1.5), Y(y_s), STRAP, 2.0)
        cv.label(X(rear - 1.5), Y(y_s) + 0.05, 'F_str (strap)', color=STRAP, size=8, bold=True)
        xr = X(ebrg + lpad / 2) + 0.03
        arrow(cv, xr, Y(h + hped + tpad / 2), xr + 0.55, Y(h + hped + tpad / 2), LOAD, 1.6)
        cv.label(xr + 0.02, Y(h + hped + tpad / 2) - 0.15, 'F_TU, F_SH, H_WS', color=LOAD, size=8, bold=True)
        # gravity loads
        arrow(cv, X(ebrg), Y(top + 0.2), X(ebrg), Y(pad_top) + 0.01, GRAV, 1.6)
        cv.label(X(ebrg) + 0.06, Y(top + 0.2) - 0.1, 'W_DCb, W_PLb', color=GRAV, size=8, bold=True)
        x_nom = lambda name: e.value(name, 'ft') - tol            # position on the nominal pile axis of an arm from O
        gravity = ((x_nom('x_cap'), h / 2, 'W_cap', 0.07), (x_nom('x_ped'), h + hped / 2, 'W_ped', 0.07),
                   (x_nom('x_bw'), h + H / 2, 'W_bw', 0.07), (e.value('dx_ck', 'ft'), h + Hck * 0.62, 'W_ck', 0.07))
        for x, y, label, dx in gravity:
            cv.circle(X(x), Y(y), 0.035, GRAV, GRAV, 0.5)
            arrow(cv, X(x), Y(y) + 0.38, X(x), Y(y) + 0.04, GRAV, 1.4, 0.08)
            cv.label(X(x) + dx, Y(y) + 0.3, label, color=GRAV, size=8, bold=True)
        # arms from O (blue)
        levels = ((-0.45, 'x_bw'), (-0.9, 'x_ck'), (-1.35, 'x_cap'), (-1.8, 'x_brg'), (-2.25, 'x_ped'))
        for level, name in levels:
            x = x_nom(name)
            cv.line([(X(x), Y(-0.02)), (X(x), Y(level - 0.08))], DIM, 0.5)
            cv.dim((X(-tol), Y(level)), (X(x), Y(level)), ((X(-tol) + X(x)) / 2, Y(level)), f'{R}.{name}', shown(name), DIM, 8)
            cv.label(max(X(x), X(-tol)) + 0.06, Y(level) - 0.04, name, color=DIM, size=8, bold=True)
        # heights above O (blue)
        # the name of each height sits under its lower end
        for xd, lo, hi, name in ((rear - 1.7, emb, y_eh, 'y_EH'), (rear - 2.9, emb, y_s, 'y_strap'), (rear - 3.8, 0, h + H, 'H_ret'),
                                 (front + 0.75, emb, pad_top, 'y_brg'), (front + 1.9, h, h + H, 'H_bw')):
            if name == 'H_bw':
                cv.line([(X(rear + tb), Y(h + H)), (X(xd + 0.1), Y(h + H))], DIM, 0.5)
            cv.dim((X(xd), Y(lo)), (X(xd), Y(hi)), (X(xd), (Y(lo) + Y(hi)) / 2), f'{R}.{name}', shown(name), DIM, 8)
            cv.label(X(xd) - 0.14, Y(lo) - 0.15, name, color=DIM, size=8, bold=True)

    def draw_strip(self, cv, eng):
        """Figure 2: the 1-ft backwall strip in the strap-slack and strap-engaged states."""
        from end_bent_walls.schematics import _geometry
        R = self.name
        g = _geometry(self.e)
        H, tb, zs = g['H'], g['tb'], g['zs']
        s = min(0.55, 3.0 / (H + 1.65))
        shown = lambda name: eng.display(name)
        cv.label(0.15, 3.75, 'BACKWALL 1-FT STRIP ABOVE THE CONSTRUCTION JOINT', color=bs.INK, size=9, bold=True)
        for x0, engaged in ((0.25, False), (3.45, True)):
            X = lambda x, x0=x0: x0 + (x + 2.4) * s
            Y = lambda y: 0.35 + (y + 0.9) * s
            cv.label(X(-0.9), Y(H + 0.75) - 0.02, 'Strap engaged' if engaged else 'Strap slack', color=bs.INK, size=10, bold=True)
            cv.rect(X(-0.6), Y(-0.75), X(1.6), Y(0), bs.GREY, 1.0)
            cv.label(X(1.15), Y(-0.5), 'cap', color=bs.GREY, size=8)
            cv.line([(X(-0.6), Y(0)), (X(1.75), Y(0))], bs.GREY, 0.7)
            cv.label(X(1.8), Y(0) + 0.02, 'joint', color=bs.GREY, size=8)
            cv.rect(X(0), Y(0), X(tb), Y(H), bs.INK, 1.6)
            cv.line([(X(0), Y(H)), (X(0), Y(0)), (X(-1.9), Y(0)), (X(-0.55), Y(H)), (X(0), Y(H))], bs.ORANGE, 1.0)
            cv.label(X(-1.0), Y(H) + 0.1, 'soil + surcharges', color=bs.ORANGE, size=8)
            face = tb if engaged else 0.0
            cv.line([(X(face), Y(0)), (X(face), Y(1.3))], bs.RED, 3.5)
            if engaged:
                cv.label(X(tb + 0.5), Y(0.5), 'tension face', color=bs.RED, size=8, bold=True)
                arrow(cv, X(0), Y(zs), X(-1.6), Y(zs), bs.TEAL, 2.0)
                cv.label(X(-1.6), Y(zs) + 0.06, 'f_str·b_s', color=bs.TEAL, size=8, bold=True)
                cv.dim((X(tb + 0.35), Y(0)), (X(tb + 0.35), Y(zs)), (X(tb + 0.35), (Y(0) + Y(zs)) / 2), f'{R}.z_strap',
                       shown('z_strap'), bs.BLUE, 8)
                cv.label(X(tb + 0.4), Y(zs) + 0.05, 'z_strap', color=bs.BLUE, size=8, bold=True)
                arc(cv, X(0.5), Y(0), 0.28, 30, 150, bs.ROSE)
                cv.label(X(0.5) - 0.12, Y(0) - 0.4, 'M_en', color=bs.ROSE, size=8, bold=True)
            else:
                arrow(cv, X(-1.2), Y(H * 0.4), X(0) - 0.01, Y(H * 0.4), bs.ROSE, 1.6)
                cv.label(X(-1.25), Y(H * 0.4) + 0.05, 'V_sl', color=bs.ROSE, size=8, bold=True)
                cv.label(X(0) - 0.6, Y(0.45), 'tension face', color=bs.RED, size=8, bold=True)
                cv.line([(X(-2.25), Y(0)), (X(-1.9), Y(0))], bs.BLUE, 0.5)
                cv.line([(X(-2.25), Y(H)), (X(-0.55), Y(H))], bs.BLUE, 0.5)
                cv.dim((X(-2.2), Y(0)), (X(-2.2), Y(H)), (X(-2.2), (Y(0) + Y(H)) / 2), f'{R}.H_bw', shown('H_bw'), bs.BLUE, 8)
                cv.label(X(-2.25), Y(H) + 0.05, 'H_bw', color=bs.BLUE, size=8, bold=True)
                arc(cv, X(0.5), Y(0), 0.28, 150, 30, bs.ROSE)
                cv.label(X(0.5) - 0.12, Y(0) - 0.4, 'M_sl', color=bs.ROSE, size=8, bold=True)

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
        values = [to_u(eng.get(n)) for n in names]
        if sheet.family[mc] == 'kr':
            env[mc] = {(int(k), j + 1): values[int(k) * len(R_KEYS) + j] for k in STATIONS for j in range(len(R_KEYS))}
        else:
            env[mc] = values
    env['A_bar'] = [to_u(eng.evaluate(f'Ab({k})')) for k in range(12)]
    env['d_bar'] = [to_u(eng.evaluate(f'Db({k})')) for k in range(12)]
    return env


def compare_envs(mine, theirs):
    """Compare the quantities both environments hold; returns (count, mismatches)."""
    count, bad = 0, []

    def one(label, a, b, floor=1e-6):
        nonlocal count
        if isinstance(a, U) and isinstance(b, U):
            count += 1
            same_dims = abs(a.d[0] - b.d[0]) < 1e-9 and abs(a.d[1] - b.d[1]) < 1e-9
            if not same_dims or not abs(a.v - b.v) <= TOL * max(abs(b.v), floor):
                bad.append((label, a, b))

    for name, a in mine.items():
        if name not in theirs:
            continue
        b = theirs[name]
        if isinstance(a, list) and isinstance(b, list):
            for i, (x, y) in enumerate(zip(a, b)):
                one(f'{name}[{i}]', x, y)
        elif isinstance(a, dict) and isinstance(b, dict):
            # the torque closes to zero at the ends, so entries that are zero up to rounding are held to the scale of the table
            scale = max((abs(v.v) for v in b.values() if isinstance(v, U)), default=1.0)
            for key in a:
                if key in b:
                    one(f'{name}{list(key)}', a[key], b[key], 1e-3 * scale)
        else:
            one(name, a, b)
    return count, bad


FUNCTION_NAMES = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin',
                  'PlotLines', 'Ab', 'Db'} | FN_NAMES


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


def in_unit(q, unit):
    """The number of a quantity in a display unit (None: it must be a plain number)."""
    if unit is None:
        if q.d != bs.NODIM:
            raise bs.BpError(f'{q!r} is not a plain number')
        return q.v
    u = bs.BpEngine().unit_q(unit)
    q.same(u, f'unit {unit}')
    return q.v / u.v


# ----------------------------------------------------------------------------- journal edition (live references)
BG = 'BridgeGeometry_2Beam'
MATERIALS = 'Materials'
JOURNAL_PATH = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
JOURNAL_SUBDIR = 'journal'                                            # end_bent_walls/bpad/journal/
REVIEW_FILE = 'End Bent Backwall Design - Journal Edition (review).bpad'
REFERENCE_CAPTION = 'shared journal value —'
JOURNAL_SECTION2 = ('Shared end-bent geometry, bearing pad data, the Span 1 expansion length and the material strengths are live references '
                    'to the journal; the owner is named beside each. The bearing actions, the strap loads and the other inputs are the '
                    'notebook case values.')
JOURNAL_PROVENANCE = ('Journal edition written by scripts/build_backwall_bpad.py --journal from the same case: the inputs the journal owns are '
                      'live references (a coherence gate compared each journal value with the notebook input before the build), and every '
                      'definition was evaluated independently and compared with the notebook to 1 part in 10⁹.')
REVIEW_BANNER = ('Review copy: the references to BridgeGeometry_2Beam, Materials and ProjectInfo resolve only inside the project journal '
                 '(D2_I95_Project_Journal.bpad). Opened on its own, this file shows them as undefined; the values stored in it are the '
                 'journal values at the time of the build.')
DROP_NAME = 'drop_bw'
DROP_REF = (f'{BG}.EndBent_backwallDrop', 'in')
#: notebook input -> (qualified journal owner, display unit): Section 2 inputs that become live references in the journal edition
JOURNAL_REFS = {
    'b_cap': (f'{BG}.EndBentCap_width', 'in'), 'h_cap': (f'{BG}.EndBentCap_depth', 'in'),
    'L_cap': (f'{BG}.EndBentCap_length', 'in'), 'L_bw': (f'{BG}.EndBentCap_length', 'in'),
    'L_load': (f'{BG}.EndBentCage_envelope', 'in'),
    'embed_pile': (f'{BG}.EndBent_pileEmbed', 'in'), 'tol_pile': (f'{BG}.EndBent_pileTolerance', 'in'),
    't_bw': (f'{BG}.Backwall_thickness_shown', 'in'), 'e_brg': (f'{BG}.EndBent_bearingOffset', 'in'),
    'h_ped': (f'{BG}.EndBentPedestal_ht', 'in'), 'B_ped': (f'{BG}.EndBentPedestal_width', 'in'),
    't_pad': (f'{BG}.Bearing_pad_thickness', 'in'), 't_ck': (f'{BG}.EndBent_cheekThickness', 'in'),
    'G_pad': (f'{BG}.Bearing_pad_G', 'ksi'), 'L_pad': (f'{BG}.Bearing_pad_length', 'in'), 'W_pad': (f'{BG}.Bearing_pad_width', 'in'),
    'n_int': (f'{BG}.Bearing_pad_internalLayers', None), 't_int': (f'{BG}.Bearing_pad_internalThickness', 'in'),
    't_cov': (f'{BG}.Bearing_pad_cover', 'in'), 'L_exp': (f'{BG}.Span_1', 'ft'),
    'fc': (f'{MATERIALS}.Substructure_fc', 'ksi'), 'fy': (f'{MATERIALS}.Rebar_fy', 'ksi'), 'Es': (f'{MATERIALS}.Rebar_Es', 'ksi'),
}
#: inputs that stay literals although the journal holds a similar quantity: name -> status, owner (reported, never compared), unit, reason
KEEP_LITERAL = {
    's_brg': dict(status='literal_incoherent_journal', owner=f'{BG}.Beam_spacing', unit='in',
                  reason='bearing spacing from the EB-XML bearing stations 29.50 / 132.49 in (102.99 in); the journal beam spacing '
                         'BridgeGeometry_2Beam.Beam_spacing is 8 ft 7 in (103 in) — the analysis value is kept'),
}
LITERAL_STATUSES = ('literal_owner_here', 'literal_incoherent_journal')
FT_IN = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*ft\s+(\d+(?:\.\d+)?)\s*in\s*$')


class JournalContext:
    """What the journal edition needs: the references, the kept literals, the externals, the stamp and the coherence rows."""

    def __init__(self, links, stamp, refs, keep, rows, externals, drop_caption):
        self.links, self.stamp, self.refs, self.keep, self.rows, self.externals = links, stamp, refs, keep, rows, externals
        self.drop, self.drop_caption = DROP_REF, drop_caption

    def apply(self, eng):
        for qualified, value in self.externals.items():
            eng.add_external(qualified, value)

    def summary(self):
        kept = [r for r in self.rows if r['status'] not in ('reference', 'reference_context')]
        return dict(rows=self.rows, references=sum(r['status'] == 'reference' for r in self.rows), literals=kept,
                    context=[r['input'] for r in self.rows if r['status'] == 'reference_context'])


def journal_number(links, owner, unit):
    """The journal value of `owner` in `unit`; a `N ft M in` literal the evaluator does not read is parsed here."""
    try:
        return in_unit(links.value(owner), unit)
    except bs.BpError:
        text = links.formula(owner)
        m = FT_IN.match(text.partition('=')[2]) if text else None
        if m and unit == 'in':
            return float(m.group(1)) * 12 + float(m.group(2))
        raise


def journal_context(links, e):
    """The coherence gate: every referenced journal value must equal the notebook input, else the build stops."""
    from scripts.build_cap_bpad import check_project_info
    stamp = check_project_info(links)                                  # {ProjectInfo.<Key>: text}, or a BuildError
    from scripts.build_cap_bpad import PROJECT_STAMP
    for name in set(JOURNAL_REFS) & set(KEEP_LITERAL):
        raise BuildError(f'{name} is both a reference and a kept literal')
    unknown = [n for n in list(JOURNAL_REFS) + list(KEEP_LITERAL) if n not in INPUT_SPEC]
    if unknown:
        raise BuildError(f'not notebook inputs: {unknown}')
    case = e.case['inputs']
    rows, bad, externals = [], [], dict(stamp)
    for mc in INPUT_SPEC:                                                # notebook input order
        if mc not in JOURNAL_REFS and mc not in KEEP_LITERAL:
            continue
        value = float(case[mc])
        shown = bs.bp_name(mc)
        if mc in JOURNAL_REFS:
            owner, unit = JOURNAL_REFS[mc]
            try:
                q = links.value(owner)
                journal_value = in_unit(q, unit)
            except bs.BpError as ex:
                bad.append(f'  {shown}: {owner} cannot be evaluated: {ex}')
                continue
            externals[owner] = q
            if not abs(journal_value - value) <= TOL * max(abs(value), 1e-12):
                bad.append(f'  {shown}: the case holds {bs.bp_num(clean(value))}{" " + unit if unit else ""} but the journal owner {owner} '
                           f'holds {bs.bp_num(clean(journal_value))}{" " + unit if unit else ""}')
            rows.append(dict(input=shown, owner=owner, journal_value=clean(journal_value), case_value=clean(value), status='reference',
                             note=f'{REFERENCE_CAPTION} {owner}' + (f' ({unit})' if unit else ' (no unit)')))
        else:
            spec = KEEP_LITERAL[mc]
            if spec['status'] not in LITERAL_STATUSES:
                raise BuildError(f'{mc}: unknown literal status {spec["status"]}')
            try:
                journal_value = journal_number(links, spec['owner'], spec['unit'])
            except bs.BpError as ex:
                bad.append(f'  {shown}: {spec["owner"]} cannot be evaluated: {ex}')
                continue
            agree = abs(journal_value - value) <= TOL * max(abs(value), 1e-12)
            if spec['status'] == 'literal_incoherent_journal' and agree:
                bad.append(f'  {shown} is kept as a literal because {spec["owner"]} disagreed, but they agree now '
                           f'({bs.bp_num(clean(value))} {spec["unit"]}): make it a reference and remove it from KEEP_LITERAL')
            rows.append(dict(input=shown, owner=spec['owner'], journal_value=clean(journal_value), case_value=clean(value),
                             status=spec['status'], note=spec['reason']))
    # the backwall top drop: the journal input the measured heights were built with (CAD TopDrop), shown as context
    from end_bent_walls.model import PROJECT_EVIDENCE
    owner, unit = DROP_REF
    drops = PROJECT_EVIDENCE['native_geometry'].get('per_bent', {}).get('top_drop_in', {})
    try:
        q = links.value(owner)
        journal_drop = in_unit(q, unit)
    except bs.BpError as ex:
        bad.append(f'  {DROP_NAME}: {owner} cannot be evaluated: {ex}')
        journal_drop = None
    if journal_drop is not None:
        externals[owner] = q
        for bent, drop in sorted(drops.items()):
            if not abs(drop - journal_drop) <= TOL * max(abs(drop), 1e-12):
                bad.append(f'  {DROP_NAME}: the journal {owner} holds {bs.bp_num(clean(journal_drop))} in but the measured CAD model '
                           f'({bent} TopDrop) holds {bs.bp_num(clean(drop))} in')
        cad_drop = clean(max(drops.values())) if drops else None
        rows.append(dict(input=DROP_NAME, owner=owner, journal_value=clean(journal_drop), case_value=cad_drop, status='reference_context',
                         note=f'{REFERENCE_CAPTION} {owner} (in); not a notebook input: the CAD backwall tops that H_bw, H_bw_edge and V_bw '
                              'are measured from were built with this drop (D-053/D-055)'))
    if bad:
        raise BuildError('coherence gate: the journal disagrees with the backwall case\n' + '\n'.join(bad))
    drop_caption = (f'{REFERENCE_CAPTION} {owner}; backwall top below the deck-top line at the front face (D-053). The CAD model measured '
                    f'for H_bw, H_bw_edge and V_bw was built with this drop (TopDrop {bs.bp_num(clean(journal_drop))} in at both end bents).')
    stamp_values = {k.partition('.')[2]: v for k, v in stamp.items()}
    if stamp_values != PROJECT_STAMP:
        raise BuildError('the ProjectInfo strings differ from PROJECT_STAMP')
    return JournalContext(links, stamp_values, dict(JOURNAL_REFS), dict(KEEP_LITERAL), rows, externals, drop_caption)


def check_journal_edition(rep, jctx):
    """Every referenced name is written as its reference and no literal remains for it; the drop reference is present once."""
    defs = {}
    for dyn in rep.iter('dynexp'):
        lhs, rhs = bs.split_definition(dyn.get('formula'))
        if lhs in defs and lhs == DROP_NAME:
            raise BuildError(f'{DROP_NAME} is defined twice')
        defs[lhs] = rhs
    for mc, (owner, unit) in jctx.refs.items():
        name = bs.bp_name(mc)
        want = owner + (f' to {unit}' if unit else '')
        if defs.get(name) != want:
            raise BuildError(f'{name} is {defs.get(name)!r} in the report; the reference {want!r} is required')
    owner, unit = jctx.drop
    if defs.get(DROP_NAME) != f'{owner} to {unit}':
        raise BuildError(f'{DROP_NAME} is {defs.get(DROP_NAME)!r}; the reference to {owner} is required')
    tables = [t for t in rep.iter('table') if t.get('name') == 'ProjectStamp']
    if len(tables) != 1:
        raise BuildError(f'the report holds {len(tables)} ProjectStamp tables, not 1')
    first = next(el for el in rep if el.tag not in ('include', 'stylerule'))
    if first.tag != 'embed' or first.find('table') is not tables[0]:
        raise BuildError('the ProjectStamp table is not the first thing after the report stylerules')
    cells = [c for c in tables[0].iter('c') if c.get('formula')]
    if [c.get('formula') for c in cells] != [f'{bs.PROJECT_INFO}.{k}' for k in bs.STAMP_KEYS]:
        raise BuildError('the ProjectStamp cells are not live ProjectInfo references')


def review_document(sheet):
    """The report alone, with the review banner after the stamp (the references do not resolve outside the journal)."""
    doc = bs.new_document()
    rep = copy.deepcopy(sheet.rep)
    stamp = next(i for i, el in enumerate(rep) if el.tag == 'embed')
    banner = bs.para(rep, REVIEW_BANNER, fontsize='10', textcolor='#8A2B1F', background='#FBE9E5', spacingafter='8')
    rep.remove(banner)
    rep.insert(stamp + 1, banner)
    doc.append(rep)
    return bs.serialize(doc)


def write_journal_outputs(links, sheet, eng, meta, out_dir=None):
    """end_bent_walls/bpad/journal/ (or `out_dir`): the fragment, the preview sidecar, the review document, coherence.json and
    verification.json; returns the verification entry."""
    base = (SIDE_DIR if out_dir is None else Path(out_dir)) / JOURNAL_SUBDIR
    (base / 'preview').mkdir(parents=True, exist_ok=True)
    shown_base = f'end_bent_walls/bpad/{JOURNAL_SUBDIR}' if out_dir is None else f'{Path(out_dir).name}/{JOURNAL_SUBDIR}'
    data = bs.serialize(sheet.rep, declaration=False).rstrip()
    (base / f'{sheet.name}.xml').write_bytes(data)
    sidecar = {name: cv.sidecar() for name, cv in sheet.canvases.items()}
    (base / 'preview' / f'{sheet.name}.canvases.json').write_text(json.dumps(sidecar, indent=1, ensure_ascii=False), encoding='utf-8',
                                                                  newline='\n')
    review = review_document(sheet)
    (base / REVIEW_FILE).write_bytes(review)
    summary = meta['journal']
    entry = entry_of(sheet, meta, data)
    entry.pop('bpad_sha256')
    entry.update({
        'fragment': f'{shown_base}/{sheet.name}.xml', 'fragment_sha256': hashlib.sha256(data).hexdigest(),
        'journal_file': links.source, 'project_stamp': {'owner': bs.PROJECT_INFO, **sheet.journal.stamp},
        'journal_references': summary['references'], 'literals_kept': [r['input'] for r in summary['literals']],
        'context_references': summary['context'],
        'references': sorted({r['owner'] for r in summary['rows'] if r['status'] in ('reference', 'reference_context')}),
        'review_document': f'{shown_base}/{REVIEW_FILE}', 'review_sha256': hashlib.sha256(review).hexdigest(),
    })
    (base / 'coherence.json').write_text(json.dumps({sheet.name: summary['rows']}, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
    (base / 'verification.json').write_bytes(json_bytes([entry]))
    return entry


def journal_line(summary):
    kept = summary['literals']
    text = f'{REPORT_NAME}: {summary["references"]} journal references verified, {len(kept)} literal{"" if len(kept) == 1 else "s"} kept'
    if kept:
        text += ' (' + '; '.join(f'{r["input"]}: journal {bs.bp_num(r["journal_value"])} vs case {bs.bp_num(r["case_value"])}' for r in kept) + ')'
    return text + f'; context references: {", ".join(summary["context"])}'


def journal_path_from(argv):
    i = argv.index('--journal')
    if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
        path = Path(argv[i + 1])
        return path if path.is_absolute() or path.exists() else ROOT / path
    return JOURNAL_PATH


# ----------------------------------------------------------------------------- build
def build(e=None, revision=None, mathcad_compare=True, extra_provenance=None, journal=None):
    """Build and verify the report: (sheet, engine, meta). `e` is an evaluated case (default: the registered one); `revision` the
    package revision text; `mathcad_compare` also builds the Mathcad worksheet of the registered case and compares both;
    `journal` (a bs.JournalLinks) builds the journal edition with live references after the coherence gate."""
    e = evaluate() if e is None else e
    rev = bm.notebook_revision() if revision is None else revision
    blocks = bm.sheet(rev)
    jctx = journal_context(journal, e) if journal is not None else None
    sheet = Sheet(e, blocks, rev, extra_provenance or (JOURNAL_PROVENANCE if jctx is not None else EXTRA_PROVENANCE))
    sheet.journal = jctx
    for blk in blocks:
        if blk.kind != 'row':
            sheet.flush()
        getattr(sheet, 'do_' + blk.kind)(blk)
    sheet.flush()
    bs.note(sheet.rep, CLOSING_NOTE, size=9)

    rep = sheet.rep
    # ---- (a) syntax and names: the engine is built from the XML that will be written
    eng = bs.BpEngine(report=REPORT_NAME)
    if jctx is not None:
        jctx.apply(eng)
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
            raise BuildError(f'{el.tag} name {el.get("name")} is also a definition')
    names = [el.get('name') for el in rep.iter('table', 'canvas', 'textcell', 'section')]
    if len(names) != len(set(names)):
        raise BuildError('duplicate table, canvas, textcell or section name')
    for cv, fill in sheet.deferred:                       # live canvases are drawn now that values exist
        fill(eng)
    for el in rep.iter('plot'):
        xs, ys = plot_items(el.get('formula'))
        for item in xs + ys:
            v = eng.evaluate(item)
            if v is not bs.NULL and (not isinstance(v, bs.Q) or v.d != bs.NODIM):
                raise BuildError(f'plot coordinate {item!r} is not a plain number')
    n_cells = bs.write_caches(rep, eng, REPORT_NAME)
    for el in rep.iter('c', 'planecontainer', 'lineardim'):
        if el.get('formula'):
            eng.evaluate(el.get('formula'))
    for el in rep.iter():
        if not isinstance(el.tag, str):
            raise BuildError('XML comment in the report')
    check_formula_rules(rep)

    # ---- (b) inputs
    case = e.case['inputs']
    for name in sheet.input_names:
        spec = INPUT_SPEC[name]
        unit = None if spec['unit'] in (None, 'bar') else bs.bp_unit(spec['unit'])
        mine = in_unit(eng.get(bs.bp_name(name)), unit)
        if not abs(mine - float(case[name])) <= INPUT_TOL * max(abs(float(case[name])), 1e-12):
            raise BuildError(f'input {name}: the sheet holds {mine!r}, the notebook {case[name]!r}')
    missing = set(INPUT_SPEC) - set(sheet.input_names) - {'N_pile', 'S_pile', 'D_pile'}
    if missing:
        raise BuildError(f'notebook inputs missing from the worksheet: {sorted(missing)}')
    if jctx is not None:
        check_journal_edition(rep, jctx)
        drop_owner, drop_unit = jctx.drop
        if abs(in_unit(eng.get(DROP_NAME), drop_unit) - in_unit(eng.get(drop_owner), drop_unit)) > INPUT_TOL:
            raise BuildError(f'{DROP_NAME} does not evaluate to {drop_owner}')

    # ---- (c) against the notebook model
    env = adapter_env(sheet, eng)
    shown = bm.comparisons(env, e)
    bad = [(n, a, b) for n, a, b in shown if abs(a - b) > TOL * max(1.0, abs(b))]
    if bad:
        raise BuildError('Blockpad values differ from the notebook:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40]))
    if len(shown) < 240:
        raise BuildError(f'only {len(shown)} comparisons with the notebook')

    # ---- (d) against the Mathcad sheet
    n_mathcad, mstatus = None, None
    if mathcad_compare:
        menv = bm.verify(bm.sheet(rev), e)
        n_mathcad, bad = compare_envs(env, menv)
        if bad:
            raise BuildError('Blockpad values differ from the Mathcad sheet:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40]))
        if n_mathcad < 200:
            raise BuildError(f'only {n_mathcad} values compared with the Mathcad sheet')
        mstatus = 'PASS' if menv['Status'] == 'PASS' else 'FAIL'

    # ---- (e) Figure 3 and the Chk strings
    expected = [dc for dc, _, _, _ in sheet.expanded_checks()]
    if sheet.chart_names != expected:
        raise BuildError('Figure 3 stems do not follow the check list')
    chart_refs = []
    for el in rep.iter('plot'):
        m = re.search(r'If\((' + re.escape(REPORT_NAME) + r'\.\w+) <= 1', el.get('formula'))
        if m:
            chart_refs.append(m.group(1).split('.', 1)[1])
    if chart_refs != expected:
        raise BuildError('Figure 3 stems reference different names than the check list')
    ratios = [eng.get(n).v for n in expected]
    if eng.get('DC_ymax').v < max(1.2, 1.1 * max(ratios)) - 1e-12:
        raise BuildError('DC_ymax does not reach the largest ratio')
    for dc, chk, _, _ in sheet.expanded_checks():
        want = FAIL_TEXT if eng.get(dc).v > 1 else PASS_TEXT
        if eng.get(chk) != want:
            raise BuildError(f'{chk} is {eng.get(chk)!r} for ratio {eng.get(dc).v}')
    status = eng.get('Status')
    if status not in (ALL_PASS, FAILURES):
        raise BuildError(f'Status {status!r}')
    if mstatus is not None and (status == ALL_PASS) != (mstatus == 'PASS'):
        raise BuildError(f'Status {status!r} disagrees with the Mathcad Status {mstatus}')
    failed = [c.key for c in e.checks if 'FAIL' in c.status]
    if (status == ALL_PASS) != (not failed):
        raise BuildError(f'Status {status!r} disagrees with the notebook checks (failing: {failed})')

    meta = dict(definitions=n_defs, functions=n_funcs, cells=n_cells, comparisons=len(shown), mathcad_values=n_mathcad, status=status,
                case_sha256=sheet.case_sha, revision=rev)
    if jctx is not None:
        meta['journal'] = jctx.summary()
    return sheet, eng, meta


def entry_of(sheet, meta, data):
    return {
        'report_name': sheet.name, 'case_sha256': meta['case_sha256'], 'package_revision': meta['revision'],
        'definitions': meta['definitions'], 'functions': meta['functions'], 'cells_and_labels': meta['cells'],
        'tool_comparisons': meta['comparisons'], 'mathcad_values_compared': meta['mathcad_values'], 'status': meta['status'],
        'bpad_sha256': hashlib.sha256(data).hexdigest(),
    }


def json_bytes(value):
    return json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True).encode('utf-8')


def write_outputs(sheet, eng, meta, out_dir=None, side_dir=None):
    """Write the document into end_bent_walls/ (or `out_dir`) and the fragment, preview sidecar and verification.json into
    end_bent_walls/bpad/ (or `side_dir`); returns the verification entry."""
    out = OUT_DIR if out_dir is None else Path(out_dir)
    side = (SIDE_DIR if out_dir is None else out / 'bpad') if side_dir is None else Path(side_dir)
    out.mkdir(parents=True, exist_ok=True)
    (side / 'fragments').mkdir(parents=True, exist_ok=True)
    (side / 'preview').mkdir(exist_ok=True)
    data = bs.serialize(sheet.doc)
    (out / FILENAME).write_bytes(data)
    (side / 'fragments' / f'{sheet.name}.xml').write_bytes(bs.serialize(sheet.rep, declaration=False).rstrip())
    sidecar = {name: cv.sidecar() for name, cv in sheet.canvases.items()}
    (side / 'preview' / f'{sheet.name}.canvases.json').write_text(json.dumps(sidecar, indent=1, ensure_ascii=False), encoding='utf-8',
                                                                  newline='\n')
    entry = entry_of(sheet, meta, data)
    entry['bpad_file'] = f'end_bent_walls/{FILENAME}' if out_dir is None else f'{out.name}/{FILENAME}'
    (side / 'verification.json').write_bytes(json_bytes([entry]))
    return entry


def distill(e, revision='working copy'):
    """(bpad bytes, verification.json bytes) of an evaluated case, for the notebook; touches no files."""
    sheet, eng, meta = build(e, revision, mathcad_compare=False, extra_provenance=NOTEBOOK_PROVENANCE)
    data = bs.serialize(sheet.doc)
    return data, json_bytes([entry_of(sheet, meta, data)])


def main_journal(argv):
    compare_mathcad = '--skip-mathcad' not in argv
    links = bs.JournalLinks.load(journal_path_from(argv))
    sheet, eng, meta = build(mathcad_compare=compare_mathcad, journal=links)
    entry = write_journal_outputs(links, sheet, eng, meta)
    mine = f'; {meta["mathcad_values"]} match the Mathcad sheet' if compare_mathcad else ''
    print(f'{journal_line(meta["journal"])}; {meta["comparisons"]} values match the notebook{mine}; Status {meta["status"]}')
    print(f'Wrote {entry["fragment"]}, {REVIEW_FILE}, coherence.json and verification.json to end_bent_walls/bpad/{JOURNAL_SUBDIR}/')
    return 0


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    if '--journal' in argv:
        return main_journal(argv)
    compare_mathcad = '--skip-mathcad' not in argv
    sheet, eng, meta = build(mathcad_compare=compare_mathcad)
    write_outputs(sheet, eng, meta)
    mine = f'; {meta["mathcad_values"]} values match the Mathcad sheet' if compare_mathcad else ''
    print(f'Wrote end_bent_walls/{FILENAME}: {meta["definitions"]} definitions, {meta["functions"]} functions; '
          f'{meta["comparisons"]} values match the notebook{mine}; Status {meta["status"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
