"""Distilled Blockpad (.bpad) report of one pile design (End Bent 1, End Bent 2, Pier).

`build(e)` returns the bytes of a Blockpad 1.9 document with one report for an Evaluation of the pile notebook model, and
`build_outputs(e)` returns everything scripts/build_pile_bpad.py writes (document, journal fragment, preview sidecar, verification
record). It is the Blockpad edition of the Mathcad worksheet of pile_design/mathcad.py and walks the same block list
(`mathcad.sheet`), so the equations, captions and sections agree. Blockpad has no vector variables, so

* the record vector (index g) becomes scalars with the suffixes _1 to _n, the strand vectors (index n) scalars _1 to _N;
* the two 121-point interaction sweeps are NOT written as formulas: Figure 2 is a picture drawn from the notebook's curve points
  while the check at the neutral-axis depth c_gov, the demands, the 5.6.4.5 route and every ratio are live formulas; the few
  values that need a search over the sweep (Mr at P = 0, the point where the demand ray meets the curve, Prx, Pry) are amber
  inputs read from the notebook.

Before anything is returned every formula is read back from the XML, evaluated by the independent Blockpad-syntax evaluator
(scripts/bpad_sheet.BpEngine) and compared with the notebook model (and with the verified Mathcad environment); the build
stops on any mismatch. Nothing here has been recalculated in Blockpad itself.

This module imports `scripts.bpad_sheet` and `pile_design.mathcad` only, so the notebook export works inside Colab.
"""
import hashlib
import importlib
import json
import math
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

from . import loads, sections
from .model import DATA_TABLE_COLUMNS, INPUT_SPEC

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:               # the checkout (or the extracted notebook package) holds scripts/
    sys.path.insert(0, str(ROOT))
from scripts import bpad_sheet as bs  # noqa: E402

REPORTS = {
    'End Bent 1': ('PileDesignEndBentOne', 'C011 - End Bent 1 Pile Design', 'End Bent 1 Pile Design.bpad'),
    'End Bent 2': ('PileDesignEndBentTwo', 'C012 - End Bent 2 Pile Design', 'End Bent 2 Pile Design.bpad'),
    'Pier': ('PileDesignPier', 'C013 - Pier Pile Design', 'Pier Pile Design.bpad'),
}
OTHER = ('PileDesignNotebook', 'Pile Design', 'Pile Design.bpad')
LEGEND = 'Inputs are highlighted amber; results are the green tables.'
PENDING_TAG = ' [pending confirmation]'
# Wording of the Mathcad edition that names the notebook or the distillation, rewritten for the submitted text (hidden notes
# keep the originals). Longer phrases first; the generic fallbacks last.
VISIBLE_RULES = [
    ('so the connection stays a PENDING item of the notebook', 'so full moment transfer at the pile head is not credited in this calculation'),
    ('Blockpad has no vector variables, so the 121-point sweep is not written as formulas.', 'The 121-point sweep is not written as formulas.'),
    ("Figure 2 is a picture of the notebook's sweep", 'Figure 2 is a picture of the interaction sweep'),
    ("The interaction curve of Figure 2 is a picture of the notebook's sweep", 'The interaction curve of Figure 2 is a picture of the interaction sweep'),
    ("The curves are a picture of the notebook's 121-point sweep", 'The curves are a picture of the 121-point interaction sweep'),
    ("The outline and strands are the notebook's layout as a picture", 'The outline and strands are drawn as a picture'),
    ('swept geometrically from 4H to 0.02H in the notebook', 'swept geometrically from 4H to 0.02H in the interaction sweep'),
    ('The notebook sweeps the curve again', 'The interaction sweep is repeated'),
    ("The angle and that point are the notebook's (amber inputs)", 'The angle and that point are read from the sweep (amber inputs)'),
    ("Check at the notebook's solved neutral-axis depth", 'Check at the solved neutral-axis depth'),
    ('The demand ray meets the notebook sweep between', 'The demand ray meets the sweep between'),
    ("The sheet takes the notebook's depth c_gov as an input", 'This calculation takes the solved depth c_gov as an input'),
    ('(read from the notebook sweep)', '(read from the interaction sweep)'),
    ('interpolated on the notebook sweep', 'interpolated on the interaction sweep'),
    ('where the demand ray meets the notebook curve', 'where the demand ray meets the interaction curve'),
    ('[from the notebook: ', '[from the interaction sweep: '),
    ('from the notebook (folded to 0-45 deg)', 'from the sweep (folded to 0-45 deg)'),
    ('(angle alpha_sh from the notebook)', '(angle alpha_sh from the sweep)'),
    ('resultant-axis curve, from the notebook', 'resultant-axis curve, from the sweep'),
    ('largest of the distilled ratios', 'largest of the check ratios'),
    ('ratio of each distilled check', 'ratio of each check'),
    ("the notebook's", 'the analysis'),
    ('the notebook', 'the pile analysis'),
    ('notebook', 'pile analysis'),
]
TOL = 1e-9
APPROX_TOL = 0.02
HOW = 'run python scripts/build_pile_bpad.py after changing the pile_design package, the registered FBMP export or the generator'

SWEEP_INDEX = {'i', 'u', 'q', 'p', 'j'}                     # ranges of the sweeps and of the sample/summary tables: not written
IGNORED_DEFS = {'P_ext_x', 'M_ext_x', 'P_ext_r', 'M_ext_r', 'P_ref_0', 'P_ref_u', 'Pl_rs', 'Ph_rs', 'Ml_rs', 'Mh_rs', 'DC_all', 'Limit',
                'ymax', 'CheckGood', 'CheckNoGood'}
FROM_NOTEBOOK = {                                           # values the Mathcad sheet finds by a search over the sweep
    'M_r_P0': 'interpolated on the notebook sweep at P = 0',
    'M_cap_u': 'interpolated on the notebook sweep at the axial load of the record',
    'P_rx': 'interpolated on the notebook sweep', 'P_ry': 'interpolated on the notebook sweep',
    'P_r_rs': 'where the demand ray meets the notebook curve', 'M_r_rs': 'where the demand ray meets the notebook curve'}
PAGE_BREAKS = {'psc': {5, 7, 9, 11, 15}, 'pipe': {5, 8, 11}}
BP_PROVENANCE = ('Blockpad edition written by pile_design/bpad.py (scripts/build_pile_bpad.py) from the same case; every definition '
                 'was evaluated independently and compared with the notebook to 1 part in 10⁹.')
FUNCTION_NAMES = {'If', 'And', 'Or', 'Not', 'Min', 'Max', 'Sqrt', 'Abs', 'Round', 'Floor', 'Tan', 'Sin', 'Cos', 'Atan', 'Asin', 'PlotLines'}


class BuildError(AssertionError):
    pass


def _mathcad():
    """The distilled Mathcad generator module (it holds the block list this edition walks)."""
    try:
        module = importlib.import_module(f'{__package__}.mathcad')
    except ImportError as exc:
        raise ImportError(f'pile_design.mathcad could not be imported ({exc})') from exc
    if not isinstance(module, ModuleType) or not callable(getattr(module, 'sheet', None)):
        raise ImportError('pile_design.mathcad is not available')
    return module


def require():
    """Raise ImportError when a collaborator of the Blockpad generator is missing (the export reports it as unavailable)."""
    _mathcad()


def report_info(e):
    return REPORTS.get(e.case['support'], OTHER)


# ----------------------------------------------------------------------------- tree helpers
def names_in(t, out=None):
    out = set() if out is None else out
    if t[0] == 'id':
        out.add(t[1])
    for part in t[1:]:
        if isinstance(part, tuple):
            names_in(part, out)
        elif isinstance(part, list):
            for p in part:
                if isinstance(p, tuple):
                    names_in(p, out)
    return out


def subst(t, mapping):
    """Tree with the free range variables in `mapping` replaced by their constant value."""
    if t[0] == 'id' and t[1] in mapping:
        return ('num', float(mapping[t[1]]))
    out = [t[0]]
    for part in t[1:]:
        if isinstance(part, tuple):
            out.append(subst(part, mapping))
        elif isinstance(part, list):
            out.append([subst(p, mapping) if isinstance(p, tuple) else p for p in part])
        else:
            out.append(part)
    return tuple(out)


def drop_v(t):
    """x[v, n] -> x[n]: the single point v = 0 of the neutral-axis check is not an index in Blockpad."""
    if t[0] == 'idx' and len(t[2]) == 2 and t[2][0] == ('id', 'v'):
        return ('idx', t[1], [drop_v(t[2][1])])
    out = [t[0]]
    for part in t[1:]:
        if isinstance(part, tuple):
            out.append(drop_v(part))
        elif isinstance(part, list):
            out.append([drop_v(p) if isinstance(p, tuple) else p for p in part])
        else:
            out.append(part)
    return tuple(out)


def literal_values(tree):
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
        for p in ([part] if isinstance(part, tuple) else part if isinstance(part, list) else []):
            if isinstance(p, tuple):
                found = literal_values(p)
                if found is not None:
                    return found
    return None


def row_args(tree):
    """The argument trees of the first row() inside tr(row(...))."""
    if tree[0] == 'call' and tree[1] == 'row':
        return tree[2]
    for part in tree[1:]:
        for p in ([part] if isinstance(part, tuple) else part if isinstance(part, list) else []):
            if isinstance(p, tuple):
                found = row_args(p)
                if found is not None:
                    return found
    return None


def has_matrix(tree):
    return row_args(tree) is not None


def unit_text(tree):
    """'kip*ft' of a tr(row(...))*(kip*ft) tree ('' when the vector is plain)."""
    if tree[0] == 'bin' and tree[1] == '*':
        q = bs._pure(tree[3])
        if q is not None and (q[1] or q[2]):
            return bs._quantity(*q).split(' ', 1)[1]
    return ''


def fnum(v):
    return f'{v:.6f}'.rstrip('0').rstrip('.') or '0'


def nice_step(span, target=6):
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag * (1 + 1e-12):
            return m * mag
    return 10 * mag


def ticks(lo, hi, target=6):
    step = nice_step(hi - lo, target)
    first = math.ceil(lo / step - 1e-9) * step
    out, v = [], first
    while v <= hi + 1e-9:
        out.append(round(v, 9))
        v += step
    return out


def tick_text(v):
    return f'{v:g}'


def text_width(text, size):
    return 0.0069 * size * len(text)


class Frame:
    """A plot area: inches on the canvas against data coordinates; fx/fy turn a Blockpad data expression into canvas-inch formulas."""

    def __init__(self, x0, x1, y0, y1, xmin, xmax, ymin, ymax):
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.xmin, self.xmax, self.ymin, self.ymax = xmin, xmax, ymin, ymax
        self.kx, self.ky = (x1 - x0) / (xmax - xmin), (y1 - y0) / (ymax - ymin)

    def X(self, v):
        return self.x0 + (v - self.xmin) * self.kx

    def Y(self, v):
        return self.y0 + (v - self.ymin) * self.ky

    def fx(self, expr):
        return f'{fnum(self.x0 - self.xmin * self.kx)}+({expr})*{fnum(self.kx)}'

    def fy(self, expr):
        return f'{fnum(self.y0 - self.ymin * self.ky)}+({expr})*{fnum(self.ky)}'


def dashed(cv, points, color, width):
    """A dashed polyline (native <lines linepattern="Dashes">), recorded for the preview like the other canvas items."""
    pts = '; '.join(f'{x:.3f}, {y:.3f}, 0' for x, y in points)
    bs.ET.SubElement(cv.el, 'lines', pts=pts, linecolor=color, linepattern='Dashes', linethickness=f'{width:g}')
    cv.items.append({'type': 'line', 'points': [[round(x, 3), round(y, 3)] for x, y in points], 'color': color, 'width': width, 'dash': 'dash'})


# ----------------------------------------------------------------------------- the sheet
class Sheet:
    """One pile's report: walks the Mathcad blocks and writes the native elements."""

    def __init__(self, e, ctx, blocks, report_name, title, pm, stamp='static'):
        self.e, self.ctx, self.blocks, self.pm = e, ctx, blocks, pm
        self.name, self.title, self.stamp = report_name, title, stamp
        self.psc = e.family == 'psc'
        self.doc = bs.new_document()
        self.rep = bs.new_report(self.doc, report_name, title)
        self.notes = None                             # the hidden WorkingNotes section (provenance, status, pending items)
        self.pending_inputs = []                      # inputs whose caption carried "[pending confirmation]"
        self.n_rec, self.n_str = len(ctx.recs), ctx.n_str
        self.tags = {'r': [str(i + 1) for i in range(self.n_rec)], 'n': [str(i + 1) for i in range(self.n_str)]}
        self.family, self.rename, self.alias = {}, {}, {}
        self.scalar_map, self.vector_map, self.matrix_map = {}, {}, {}
        self.dropped = set(IGNORED_DEFS)
        self.pending = []                             # (family, item, [(tag, formula)]) of the rows after the first
        self.sec, self.flushes = 0, 0
        self.pending_vec_inputs = []
        self.rec_labels = []
        self.deferred, self.canvases = [], {}
        self.chart_names = []
        self.after_plot = False
        self.in_fig3_data = False
        self.fig2 = None
        self.from_notebook = []
        self.summary_done = False

    # -- scalar names
    def vname(self, base):
        return bs.bp_name(self.rename.get(base, base))

    def register(self, base, family):
        self.family[base] = family
        if family == 'v':
            self.vector_map[base] = [self.alias.get(base, self.vname(base))]
        else:
            self.vector_map[base] = [self.sname(base, t) for t in self.tags[family if family != 'nv' else 'n']]

    def sname(self, base, tag):
        return f'{self.vname(base)}_{tag}'

    def scal(self, base, idx):
        fam = self.family.get(base)
        if fam is None:
            return None
        if idx is None:
            return list(self.vector_map[base])
        if fam == 'v':
            return self.alias.get(base, self.vname(base))
        if not isinstance(idx, int):
            raise BuildError(f'{base}[{idx}] reached the emitter with a free index')
        return self.sname(base, self.tags['r' if fam == 'r' else 'n'][idx])

    def formula_of(self, tree, mapping=None):
        tree = drop_v(subst(tree, mapping or {}))
        return bs.bp_formula(tree, self.scal)

    def item_formula(self, name, tree, unit, mapping=None):
        text = f'{name} = {self.formula_of(tree, mapping)}'
        u = bs.bp_unit(unit)
        return text + (f' to {u}' if u else '')

    def eq(self, parent, formula, caption='', style=None, show_result=True, inline=False):
        return bs.equation(parent, formula, caption, style=style, show_result=show_result, inline=inline)

    # -- plain blocks
    def do_title(self, blk):
        if self.stamp:                                # the project stamp first: static text, or live ProjectInfo.* references
            bs.project_stamp_table(self.rep, bs.PROJECT_STAMP, live=self.stamp == 'live')
        bs.para(self.rep, 'D2 I-95 PEDESTRIAN BRIDGE', fontsize=16, fontweight='bold', spacingafter=2)
        bs.para(self.rep, self.title, fontsize=14, fontweight='bold', spacingafter=6)
        self.notes = bs.working_notes(self.rep)       # the working language of the title block goes here, hidden

    def do_h1(self, blk):
        self.flush()
        self.sec = int(blk.payload.split('.')[0])
        bs.heading(self.rep, blk.payload, page_break=self.sec in PAGE_BREAKS[self.e.family])

    def do_h2(self, blk):
        self.flush()
        text = blk.payload
        if text.startswith('Sample of the sweep'):
            text = 'Moment resistance at zero axial load (read from the notebook sweep)'
        bs.subheading(self.rep, text)

    @staticmethod
    def renumber(text):
        return re.sub(r'\(index (\d+)\)', lambda m: f'(record {int(m.group(1)) + 1})', text)

    def do_p(self, blk):
        text = blk.payload
        if text.startswith('Figure 3 data'):
            self.in_fig3_data = True
            return
        if text.startswith('Distilled from'):
            if self.stamp == 'live':                  # the journal edition is tied to its case alone, not to the package revision
                text = re.sub(r' \(package [0-9a-f]+\)', '', text)
            bs.para(self.notes, text + ' ' + BP_PROVENANCE)                              # provenance: hidden
            return
        if text.startswith('Status:'):
            bs.para(self.notes, text.split(' Inputs are highlighted')[0])                 # tool status: hidden
            text = LEGEND
        elif text.startswith('Governing records of'):
            text = text.replace('(index g)', f'(records 1 to {self.n_rec})')
        elif text.startswith('The ray meets the sweep'):
            text = ('The demand ray meets the notebook sweep between two neighbouring points; the neutral-axis depth there is interpolated. '
                    'The sheet takes the notebook\'s depth c_gov as an input and evaluates the section exactly at c_gov '
                    '(no interpolation between sweep points). The 121-point sweep itself is not written as formulas (see Section 7).')
        elif text.startswith('The demand moment is resisted'):
            text = ('The demand moment is resisted about the axis of the resultant moment. The notebook sweeps the curve again with the section '
                    'rotated by the folded angle alpha (0 to 45 degrees, the square being symmetric); the demand ray from the origin meets the '
                    'phi-curve at (Pr, Mr) and D/C = Mu / Mr along the ray. The angle and that point are the notebook\'s (amber inputs); '
                    'tan(alpha) = M_min / M_max proves the angle, and the check at c_gov below recomputes the section.')
        bs.para(self.rep, self.renumber(text))

    def do_note(self, blk):
        text = blk.payload
        if text.startswith('Columns, left to right'):
            return
        if text.startswith('The strand coordinates x_st'):
            text = (f'The strand coordinates are scalars: x_st_1 to x_st_{self.n_str} and y_st_1 to y_st_{self.n_str}. Strand 1 is written out, '
                    f'strands 2 to {self.n_str} are in the collapsed section, and the strand table in Section 9 lists them all.')
        text = text.replace('the distilled ratios below do not close them', 'the distilled ratios above do not close them')
        if text.startswith(('The notebook lists', 'No item is pending.')):             # pending-item bookkeeping: hidden
            bs.note(self.notes, text)
            return
        if ' The distilled Status covers' in text:                                       # FBMP model D/C stays; the status caveat hides
            visible, _, caveat = text.partition(' The distilled Status covers')
            bs.note(self.notes, 'The Status covers' + caveat)
            if not visible.strip():
                return
            text = visible
        if self.after_plot:
            bs.note(self.rep, text, background='#F1F5FA')
        else:
            bs.note(self.rep, text)

    def do_bullets(self, blk):
        items = list(blk.payload)
        for i, item in enumerate(items):
            if item.startswith('Every worksheet equation is parsed once'):
                bs.para(self.notes, '• Every definition was read back from the XML and evaluated by an independent Blockpad-syntax '
                                    'evaluator, then compared with the notebook (and with the Mathcad worksheet) before the file was '
                                    'written. Governing records, the notebook angles, the neutral-axis depth c_gov and the few values '
                                    'found by a search over the interaction sweep are amber inputs read from the notebook.', spacingafter=4)
                continue
            if item.startswith('FBMP source:'):
                bs.para(self.notes, '• ' + item, spacingafter=4)                         # file hash and register id: hidden
                item = re.sub(r'^FBMP source: (.*?), SHA-256 [0-9a-f]+ \([^)]*\)\. ', r'FBMP analysis: \1. ', item)
            elif item.startswith('The interaction curve is swept live'):
                item = ('The interaction curve of Figure 2 is a picture of the notebook\'s sweep. The 5.6.4.5 route, the resultant-axis check at c_gov, '
                        'the demands and every ratio are live formulas.')
            elif item.startswith('Strain is linear with the extreme compression fiber'):
                item = item.replace('swept geometrically from 4H to 0.02H', 'swept geometrically from 4H to 0.02H in the notebook')
            elif item.startswith('Pn is held between'):
                item = item.split(' The pure-compression')[0] + ' The pure-compression and pure-tension points are scalars below.'
            elif item.startswith('Figure 2 is a picture'):
                item = ('Blockpad has no vector variables, so the 121-point sweep is not written as formulas. Figure 2 is a picture of the notebook\'s '
                        'sweep. Section 9 evaluates the same equations (strain, power-formula stress, block geometry, Pn, Mn, phi, Pr, Mr) at the '
                        'single neutral-axis depth c_gov, strand by strand.')
            bs.para(self.rep, '• ' + self.renumber(item), spacingafter=4)

    def do_inputs(self, blk):
        bs.para(self.rep, blk.opts['title'], fontweight='bold', spacingbefore='4', spacingafter='3', keepwithnext='True')
        for it in blk.payload:
            self.input_item(it)

    def input_item(self, it):
        name = bs.bp_name(it.name)
        caption = it.caption
        if caption.endswith(PENDING_TAG):             # the confirmation status is bookkeeping: hidden notes list the inputs
            caption = caption[:-len(PENDING_TAG)]
            self.pending_inputs.append(name)
        self.scalar_map[it.name] = name
        self.eq(self.rep, f'{name} = {self.formula_of(it.tree)}', caption, style='Required Input', show_result=False,
                inline=bool(caption) and len(caption) <= 45)

    # -- eqs and rows
    def do_eqs(self, blk):
        if self.in_fig3_data:
            return
        self.walk(blk.payload)

    do_row = do_eqs

    def walk(self, items):
        if all(it.kind == 'show' for it in items):
            exprs = [it.expr for it in items]
            if exprs and exprs[0] == 'Rec':
                self.demand_results_table()
            return
        for it in items:
            if it.kind == 'input' and has_matrix(it.tree):
                self.pending_vec_inputs.append(it)
                continue
            self.flush_vec_inputs()
            self.item(it)
        self.flush_vec_inputs()
        self.flush()

    def item(self, it):
        k = it.kind
        if k in ('range', 'show'):
            return
        if k == 'input':
            return self.do_I(it)
        if k == 'eq':
            return self.do_E(it)
        if k == 'def':
            return self.do_D(it)
        if k == 'idef':
            return self.do_V(it)
        raise BuildError(f'unhandled item {k} {it.name}')

    def do_I(self, it):
        self.input_item(it)

    def depends_on_dropped(self, it):
        return bool(names_in(it.tree) & self.dropped)

    def do_E(self, it):
        n = it.name
        if n == 'Status':
            return
        if n == 'DC_max':
            return self.summary()
        if n in FROM_NOTEBOOK:
            return self.notebook_input(it)
        tree = it.tree
        if tree[0] == 'idx' and tree[1][0] == 'id' and self.family.get(tree[1][1]) == 'v':
            self.scalar_map[n] = self.scal(tree[1][1], 0)           # P_n_cg = P_n_p[0]: the c_gov vector item already carries the name
            return
        if self.depends_on_dropped(it):
            self.dropped.add(n)
            return
        name = bs.bp_name(n)
        self.scalar_map[n] = name
        self.eq(self.rep, self.item_formula(name, tree, it.unit), it.caption)
        if n == 'w_tens':
            self.shear_strand_table()
        if n == 'DC_cg':
            self.strand_table()
            if self.fig2 is not None:
                self.emit_fig2()

    def notebook_input(self, it):
        name = bs.bp_name(it.name)
        unit = bs.bp_unit(it.unit)
        value = self.e.value(it.name, it.unit)
        self.scalar_map[it.name] = name
        self.from_notebook.append(it.name)
        caption = f'{it.caption} [from the notebook: {FROM_NOTEBOOK[it.name]}]'
        self.eq(self.rep, f'{name} = {bs.bp_num(value)} {unit}', caption, style='Required Input', show_result=False)

    def do_D(self, it):
        n = it.name
        if n == 'Rec':
            self.rec_labels = literal_values(it.tree)
            return
        if n == 'gamma_g':
            self.register(n, 'r')
            args = row_args(it.tree)
            rest = []
            for k, arg in enumerate(args):
                formula = f'{self.sname(n, self.tags["r"][k])} = {bs.bp_formula(arg, self.scal)}'
                if k == 0:
                    self.eq(self.rep, formula, 'drag-load factor of each record')
                else:
                    rest.append((self.tags['r'][k], formula))
            self.pending.append(('r', SimpleNamespace(caption='drag-load factor of each record', show=True), rest))
            return
        if n in IGNORED_DEFS or re.fullmatch(r'DC_m\d+', n) or self.depends_on_dropped(it):
            self.dropped.add(n)
            return
        name = bs.bp_name(n)
        self.scalar_map[n] = name
        self.eq(self.rep, self.item_formula(name, it.tree, None), it.caption)

    def do_V(self, it):
        idx = it.index
        key = idx[0] if isinstance(idx, tuple) else idx
        if key in SWEEP_INDEX:
            self.dropped.add(it.name)
            return
        if self.depends_on_dropped(it):
            self.dropped.add(it.name)
            return
        if key == 'v':
            return self.do_Vv(it)
        fam = {'r': 'r', 'n': 'n'}.get(key)
        if fam is None:
            raise BuildError(f'unhandled range {idx} for {it.name}')
        self.register(it.name, fam)
        tags = self.tags[fam]
        first = self.item_formula(self.sname(it.name, tags[0]), it.tree, it.unit, {key: 0})
        self.eq(self.rep, first, it.caption, show_result=it.show)
        rest = [(t, self.item_formula(self.sname(it.name, t), it.tree, it.unit, {key: k})) for k, t in enumerate(tags) if k > 0]
        self.pending.append((fam, it, rest))

    def do_Vv(self, it):
        """An item of the single-point check at c_gov: index v (scalar) or (v, n) (one scalar per strand)."""
        n = it.name
        matrix = isinstance(it.index, tuple)
        new = re.sub(r'_p(\d*)$', lambda m: '_cg' + m.group(1), n)
        if n == 'c_p':                                  # c_p[v] = c_gov
            self.family[n] = 'v'
            self.alias[n] = 'c_gov'
            self.vector_map[n] = ['c_gov']
            return
        self.rename[n] = new
        if not matrix:
            self.register(n, 'v')
            name = self.scal(n, 0)
            self.scalar_map[n] = name
            self.eq(self.rep, self.item_formula(name, it.tree, it.unit), it.caption, show_result=it.show)
            return
        self.register(n, 'nv')
        tags = self.tags['n']
        first = self.item_formula(self.sname(n, tags[0]), it.tree, it.unit, {'n': 0})
        self.eq(self.rep, first, it.caption, show_result=it.show)
        rest = [(t, self.item_formula(self.sname(n, t), it.tree, it.unit, {'n': k})) for k, t in enumerate(tags) if k > 0]
        self.pending.append(('n', it, rest))

    # -- hidden sections
    def flush(self):
        if not self.pending:
            return
        self.flushes += 1
        groups = {}
        for fam, it, rest in self.pending:
            groups.setdefault(fam, []).append((it, rest))
        self.pending = []
        for fam, items in groups.items():
            count = self.n_rec if fam == 'r' else self.n_str
            word = 'Records' if fam == 'r' else 'Strands'
            if count < 2:
                continue
            bs.note(self.rep, f'{word} 2 to {count}: the same equations, collapsed.')
            sec = bs.section(self.rep, f'{word}2toN_{self.flushes}')
            for j in range(count - 1):
                for it, rest in items:
                    if j < len(rest):
                        self.eq(sec, rest[j][1], it.caption, show_result=getattr(it, 'show', True))

    def flush_vec_inputs(self):
        items, self.pending_vec_inputs = self.pending_vec_inputs, []
        if not items:
            return
        e = self.e
        headers, rows = ['Record'], []
        columns = []
        for it in items:
            self.register(it.name, 'r')
            unit = unit_text(it.tree)
            columns.append((it, literal_values(it.tree), unit))
            headers.append(f'{bs.bp_name(it.name)} ({unit})' if unit else bs.bp_name(it.name))
        for k, tag in enumerate(self.tags['r']):
            label = f'{tag}. {self.rec_labels[k]}' if k < len(self.rec_labels) else tag
            cells = [label]
            for it, values, unit in columns:
                cells.append(('define', f'{self.sname(it.name, tag)} = {bs.bp_num(values[k])}' + (f' {unit}' if unit else ''), 'Required Input'))
            rows.append(cells)
        bs.para(self.rep, 'Governing FBMP records, one row per check (inputs read from the export)', fontweight='bold', spacingbefore='4',
                spacingafter='3', keepwithnext='True')
        bs.table(self.rep, 'DemandInputs', headers, rows, [120] + [88] * len(columns), 'input', font='9')

    # -- tables
    def demand_results_table(self):
        rows = []
        for k, tag in enumerate(self.tags['r']):
            rows.append([f'{tag}. {self.rec_labels[k]}' if k < len(self.rec_labels) else tag, ('formula', f'P_fbmp_{tag} to kip'),
                         ('formula', f'P_u_{tag} to kip'), ('formula', f'M_res_{tag} to kip*ft'), ('formula', f'V_res_{tag} to kip')])
        bs.table(self.rep, 'DemandResults', ['Record', 'P_fbmp (kip)', 'P_u incl. DR (kip)', 'M_res (kip-ft)', 'V_res (kip)'], rows,
                 [150, 90, 100, 90, 90], 'output')

    def strand_table(self):
        rows = []
        for tag in self.tags['n']:
            s = lambda base: self.sname(base, tag)
            rows.append([f'Strand {tag}', ('formula', s('x_st') + ' to in'), ('formula', s('y_st') + ' to in'), ('formula', s('s_st_r') + ' to in'),
                         ('formula', s('d_st_r') + ' to in'), ('formula', s('eps_p_p')), ('formula', s('f_p_p') + ' to ksi')])
        bs.para(self.rep, 'Strand table: coordinates, depth below the extreme compression fiber, strain and stress at c_gov', fontweight='bold',
                spacingbefore='4', spacingafter='3', keepwithnext='True')
        bs.table(self.rep, 'StrandTable', ['Strand', 'x (in)', 'y (in)', 's (in)', 'd (in)', 'strain', 'stress (ksi)'], rows,
                 [90, 70, 70, 70, 70, 80, 80], 'output')

    def shear_strand_table(self):
        rows = []
        for tag in self.tags['n']:
            s = lambda base: self.sname(base, tag)
            rows.append([f'Strand {tag}', ('formula', s('s_sh') + ' to in'), ('formula', s('m_sh')), ('formula', s('w_sh') + ' to in')])
        bs.table(self.rep, 'ShearStrandTable', ['Strand', 's (in)', 'on tension half (1)', 'w (in)'], rows, [110, 100, 150, 100], 'output')

    # -- summary
    def checks(self):
        return [(name, 'Chk_' + name[3:], text) for name, _, text in self.pm.summary_checks(self.e)]

    def summary(self):
        names = [dc for dc, _, _ in self.checks()]
        self.scalar_map['DC_max'] = 'DC_max'
        self.eq(self.rep, 'DC_max = Max(' + ', '.join(names) + ')', 'largest of the check ratios')
        self.eq(self.rep, 'Status = If(DC_max <= 1, "✓ All Checks Pass", "⊗ There are FAILURES")', 'numerical checks of this calculation', style='Result only')
        sec = bs.section(self.rep, 'Checks')
        for dc, chk, _ in self.checks():
            self.eq(sec, f'{chk} = If({dc} <= 1, "✓ PASS", "⊗ FAIL")')
        rows = [[f'{i + 1}. {text}', ('formula', dc), ('formula', chk)] for i, (dc, chk, text) in enumerate(self.checks())]
        rows.append(['OVERALL', ('formula', 'DC_max'), ('formula', 'Status')])
        bs.table(self.rep, 'Summary', ['Check', 'D/C', 'Result'], rows, [300, 90, 130], 'output')
        self.summary_done = True

    def do_plot(self, blk):
        self.in_fig3_data = False
        self.after_plot = True
        names = [dc for dc, _, _ in self.checks()]
        self.chart_names = names
        self.eq(self.rep, 'DC_ymax = Max(1.2, 1.1*Max(' + ', '.join(names) + '))', 'vertical scale of Figure 3')
        cv = bs.canvas(self.rep, 'DCChart', 'D/C by check', 3.2)
        self.canvases['DCChart'] = cv
        self.deferred.append((cv, lambda eng, cv=cv: self.draw_chart(cv, eng)))
        bs.note(self.rep, 'Figure 3. Demand/capacity ratio of each check (stems) against the 1.0 limit. The stems are live '
                          'formulas of the check ratios: a stem turns red when its ratio passes 1.0.')

    # -- figures
    def do_fig(self, blk):
        name = blk.payload
        if name.endswith('_section'):
            cv = bs.canvas(self.rep, 'Figure1Section', 'Pile section', 4.2)
            self.canvases['Figure1Section'] = cv
            self.deferred.append((cv, lambda eng, cv=cv: self.draw_section(cv, eng)))
            tail = (' The outline and strands are the notebook\'s layout as a picture; the dimensions and the bending-axis angles are live.'
                    if self.psc else ' The ring is a picture; the outside diameter and the design wall thickness are live.')
            bs.note(self.rep, blk.opts['caption'] + tail)
            return
        if self.psc:
            self.fig2 = blk                              # drawn after the check at c_gov, where every demand it shows is defined
        else:
            self.emit_fig2(blk)

    def emit_fig2(self, blk=None):
        blk = blk or self.fig2
        self.fig2 = None
        cv = bs.canvas(self.rep, 'Figure2Interaction', 'Interaction diagram' if self.psc else 'Combined axial load and flexure', 5.1)
        self.canvases['Figure2Interaction'] = cv
        fill = self.draw_interaction if self.psc else self.draw_envelope
        self.deferred.append((cv, lambda eng, cv=cv: fill(cv, eng)))
        if self.psc:
            bs.note(self.rep, 'Figure 2. Interaction diagram: factored curves for bending parallel to a face and about the governing resultant axis, '
                              'the nominal curve (dashed) and the governing demand points. The curves are a picture of the notebook\'s '
                              f'{self.e.case["inputs"]["n_sweep"]:g}-point sweep and do not move when an input changes; the check at c_gov (Section 9), the '
                              'demands, the phi Pn,max line and the demand points are live.')
        else:
            bs.note(self.rep, 'Figure 2. Combined axial load and flexure: the bilinear envelope of LRFD 6.9.2.2.1 (compression and tension) from the live '
                              'corner values, with the governing records as live points.')

    def label_row(self, cv, eng, x, y, parts, size=8, color=bs.INK):
        """Static text and live numbers on one line: parts are text or ('live', formula)."""
        for part in parts:
            if isinstance(part, tuple):
                shown = eng.format_value(eng.evaluate(part[1]))
                cv.label(x, y, formula=part[1], shown=shown, color=color, size=size)
                x += text_width(shown, size) + 0.06
            else:
                cv.label(x, y, part, color=color, size=size)
                x += text_width(part, size) + 0.05

    def draw_section(self, cv, eng):
        e, R, p = self.e, self.name, self.e.case['inputs']
        if self.psc:
            D = p['D_pile']
            k = 2.7 / D
            x0, y0 = 1.1, 0.85
            x1, y1 = x0 + 2.7, y0 + 2.7
            cv.label(0.15, 4.05, f'PILE SECTION — {D:g} in square, {e.details["option"]["count"]} strands, Index {e.case["psc"]["index"]}, pattern {e.case["psc"]["pattern"]}',
                     color=bs.INK, size=9)
            cv.rect(x0, y0, x1, y1, bs.INK, 1.8)
            d = p['d_edge']
            cv.rect(x0 + d * k, y0 + d * k, x1 - d * k, y1 - d * k, bs.GREY, 0.6)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cv.line([(x0 - 0.15, cy), (x1 + 0.15, cy)], '#AAB4BD', 0.5)
            cv.line([(cx, y0 - 0.15), (cx, y1 + 0.15)], '#AAB4BD', 0.5)
            r = math.sqrt(e.details['option']['strand_area_in2'] / math.pi) * 1.6 * k
            for sx, sy in e.details['layout']:
                cv.circle(cx + sx * k, cy + sy * k, r, bs.ROSE, '#7B241C', 0.6)
            reach = D / 2 * 1.3 * k
            for idx, color, text in ((2, bs.TEAL, 'resultant-moment bending axis'), (3, bs.BLUE, 'shear-record bending axis')):
                a = self.pm.bending_axis_of(self.ctx.recs[self.ctx.idx['psc_flex_res' if idx == 2 else 'psc_shear']][2])
                dashed(cv, [(cx - reach * math.cos(a), cy - reach * math.sin(a)), (cx + reach * math.cos(a), cy + reach * math.sin(a))], color, 1.1)
            cv.dim((x0, y0), (x1, y0), ((x0 + x1) / 2, y0 - 0.38), f'{R}.D_pile', eng.format_value(eng.get('D_pile'), 'in'), '#5D6F80')
            cv.dim((x0, y1), (x0 + d * k, y1), (x0 + d * k / 2, y1 + 0.28), f'{R}.d_edge', eng.format_value(eng.get('d_edge'), 'in'), bs.ROSE)
            lx = x1 + 0.3
            cv.line([(lx, 3.05), (lx + 0.35, 3.05)], bs.TEAL, 1.4)
            self.label_row(cv, eng, lx + 0.42, 3.01, ['resultant axis, alpha =', ('live', f'{R}.alpha_rs/(1 deg)'), 'deg'], 8)
            cv.line([(lx, 2.8), (lx + 0.35, 2.8)], bs.BLUE, 1.4)
            self.label_row(cv, eng, lx + 0.42, 2.76, ['shear-record axis, alpha =', ('live', f'{R}.alpha_sh/(1 deg)'), 'deg'], 8)
            cv.label(lx, 1.55, 'red circles: prestressing strands', color=bs.ROSE, size=8)
            cv.label(lx, 1.35, 'grey square: strand centre line', color=bs.GREY, size=8)
        else:
            D, t = p['D_out'], p['t_wall'] - p['t_corr']
            k = 2.7 / D
            cx, cy = 3.0, 2.2
            cv.label(0.15, 4.05, f'PIPE SECTION — {D:g} in x {p["t_wall"]:g} in wall, Fy = {p["Fy"]:g} ksi', color=bs.INK, size=9)
            cv.circle(cx, cy, D / 2 * k, '#C9D3DC', bs.INK, 1.6)
            cv.circle(cx, cy, (D / 2 - t) * k, '#FFFFFF', bs.INK, 1.0)
            cv.dim((cx - D / 2 * k, cy - D / 2 * k - 0.1), (cx + D / 2 * k, cy - D / 2 * k - 0.1), (cx, cy - D / 2 * k - 0.5), f'{R}.D_out',
                   eng.format_value(eng.get('D_out'), 'in'), '#5D6F80')
            self.label_row(cv, eng, cx + D / 2 * k + 0.2, cy + 0.2, ['design wall t =', ('live', f'{R}.t_des/(1 in)'), 'in'], 9, bs.ROSE)
            cv.label(cx + D / 2 * k + 0.2, cy, 'after the corrosion allowance', color=bs.GREY, size=8)

    def curve_bounds(self, rows, demands):
        mmax = max(max(r[0]) for r in rows)
        mmax = max([mmax] + [m for m, _ in demands])
        pmax = max(max(r[1]) for r in rows)
        pmin = min(min(r[1]) for r in rows)
        pmax = max([pmax] + [pp for _, pp in demands])
        pmin = min([pmin] + [pp for _, pp in demands])
        return mmax, pmin, pmax

    def make_frame(self, cv, mmax, pmin, pmax, left=0.95, right=6.3, bottom=1.55, top=4.5):
        mstep = nice_step(mmax * 1.03, 6)
        xmax = math.ceil(mmax * 1.03 / mstep - 1e-9) * mstep
        span = pmax - pmin
        pstep = nice_step(span * 1.08, 6)
        ymin = math.floor((pmin - 0.03 * span) / pstep + 1e-9) * pstep
        ymax = math.ceil((pmax + 0.05 * span) / pstep - 1e-9) * pstep
        pt = ticks(ymin, ymax, 6)
        fr = Frame(left, right, bottom, top, 0.0, xmax, ymin, ymax)
        cv.rect(fr.x0, fr.y0, fr.x1, fr.y1, bs.INK, 1.0)
        for v in ticks(0, fr.xmax, 6):
            x = fr.X(v)
            cv.line([(x, fr.y0), (x, fr.y1)], '#E3E8EC', 0.5)
            cv.label(x - 0.04 * len(tick_text(v)), fr.y0 - 0.17, tick_text(v), color=bs.INK, size=8)
        for v in pt:
            y = fr.Y(v)
            cv.line([(fr.x0, y), (fr.x1, y)], '#E3E8EC', 0.5)
            cv.label(fr.x0 - 0.1 - 0.075 * len(tick_text(v)), y - 0.04, tick_text(v), color=bs.INK, size=8)
        if fr.ymin < 0 < fr.ymax:
            cv.line([(fr.x0, fr.Y(0)), (fr.x1, fr.Y(0))], bs.INK, 0.8)
        cv.label(fr.x0 + 1.6, fr.y0 - 0.36, 'Moment, kip-ft', color=bs.INK, size=8)
        cv.label(0.15, fr.y1 + 0.1, 'Axial load, kip (compression +)', color=bs.INK, size=8)
        return fr

    def live_cross(self, cv, eng, fr, g, color):
        R = self.name
        m, p_ = f'{R}.M_res_{g}/(1 kip*ft)', f'{R}.P_u_{g}/(1 kip)'
        for dx, dy in ((0.07, 0.0), (0.0, 0.07)):
            xs = [f'{fr.fx(m)}-{dx}', f'{fr.fx(m)}+{dx}'] if dx else [fr.fx(m)] * 2
            ys = [f'{fr.fy(p_)}-{dy}', f'{fr.fy(p_)}+{dy}'] if dy else [fr.fy(p_)] * 2
            cv.plot(xs, ys, color, 1.8, [(eng.evaluate(x).v, eng.evaluate(y).v) for x, y in zip(xs, ys)])

    def draw_interaction(self, cv, eng):
        e, R = self.e, self.name
        c0, cr = e.curve, e.curve['resultant']
        recs = self.ctx.recs
        gs = [(self.ctx.idx[k], k, color) for k, color in (('psc_axial', '#6C3483'), ('psc_flex_bi', bs.RED), ('psc_flex_res', '#117A65'))]
        demands = [(recs[g][2]['M_res'], recs[g][2]['P_u']) for g, _, _ in gs]
        rows = [(c0['Mr'], c0['Pr']), (c0['Mn'], c0['Pn']), (cr['Mr'], cr['Pr'])]
        mmax, pmin, pmax = self.curve_bounds(rows, demands)
        cv.label(0.15, 4.92, 'INTERACTION DIAGRAM — picture of the notebook sweep, live check points', color=bs.INK, size=9, bold=True)
        fr = self.make_frame(cv, mmax, pmin, pmax)
        dashed(cv, [(fr.X(m), fr.Y(p_)) for m, p_ in zip(c0['Mn'], c0['Pn'])], bs.GREY, 1.0)
        cv.line([(fr.X(m), fr.Y(p_)) for m, p_ in zip(c0['Mr'], c0['Pr'])], bs.BLUE, 1.8)
        cv.line([(fr.X(m), fr.Y(p_)) for m, p_ in zip(cr['Mr'], cr['Pr'])], bs.TEAL, 1.5)
        # phi Pn,max: a live horizontal line
        ypm = fr.fy(f'{R}.P_r_max/(1 kip)')
        cv.plot([fnum(fr.x0), fnum(fr.x1)], [ypm, ypm], bs.ROSE, 1.0, [(fr.x0, eng.evaluate(ypm).v), (fr.x1, eng.evaluate(ypm).v)])
        for g, _, color in gs:
            self.live_cross(cv, eng, fr, g + 1, color)
        # legend
        y = 1.0
        for color, text in ((bs.BLUE, 'factored, parallel to a face'), (bs.TEAL, 'factored, resultant axis'),
                            (bs.GREY, 'nominal, parallel to a face (dashed)')):
            if color == bs.GREY:
                dashed(cv, [(0.5, y + 0.03), (0.9, y + 0.03)], color, 1.5)
            else:
                cv.line([(0.5, y + 0.03), (0.9, y + 0.03)], color, 1.5)
            cv.label(1.0, y, text, color=bs.INK, size=8)
            y -= 0.2
        y2 = 1.0
        cv.line([(3.3, y2 + 0.03), (3.65, y2 + 0.03)], bs.ROSE, 1.0)
        self.label_row(cv, eng, 3.75, y2, ['phi Pn,max', ('live', f'{R}.P_r_max/(1 kip)'), 'kip'], 8)
        y2 -= 0.2
        for (g, key, color), short in zip(gs, ('axial', '5.6.4.5', 'resultant')):
            cv.line([(3.3, y2 + 0.03), (3.65, y2 + 0.03)], color, 1.8)
            self.label_row(cv, eng, 3.75, y2, [short + ': Pu', ('live', f'{R}.P_u_{g + 1}/(1 kip)'), 'kip, Mu', ('live', f'{R}.M_res_{g + 1}/(1 kip*ft)'), 'kip-ft'], 8)
            y2 -= 0.2

    def draw_envelope(self, cv, eng):
        e, R = self.e, self.name
        recs = self.ctx.recs
        gs = [(self.ctx.idx[k], color) for k, color in (('pipe_axial', '#6C3483'), ('pipe_comb', bs.RED), ('pipe_tension', '#117A65')) if k in self.ctx.idx]
        Pr, Mr, Pt = e.value('P_r_comb', 'kip'), e.value('M_r', 'kip*ft'), e.value('P_r_t', 'kip')
        demands = [(recs[g][2]['M_res'], recs[g][2]['P_u']) for g, _ in gs]
        mmax, pmin, pmax = self.curve_bounds([([0, Mr], [Pr, -Pt])], demands)
        cv.label(0.15, 4.92, 'COMBINED AXIAL LOAD AND FLEXURE — LRFD 6.9.2.2.1 envelope, live corner values', color=bs.INK, size=9, bold=True)
        fr = self.make_frame(cv, mmax, pmin, pmax)
        mr, prc, prt = f'{R}.M_r/(1 kip*ft)', f'{R}.P_r_comb/(1 kip)', f'{R}.P_r_t/(1 kip)'
        corner = f'0.9*{mr}'
        for ys, color in (([prc, f'0.2*{prc}', '0'], bs.BLUE), ([f'-{prt}', f'-0.2*{prt}', '0'], '#2C7FB8')):
            xs_f = [fr.fx('0'), fr.fx(corner), fr.fx(mr)]
            ys_f = [fr.fy(v) for v in ys]
            cv.plot(xs_f, ys_f, color, 1.8, [(eng.evaluate(x).v, eng.evaluate(y).v) for x, y in zip(xs_f, ys_f)])
        for g, color in gs:
            self.live_cross(cv, eng, fr, g + 1, color)
        y = 1.0
        cv.line([(0.5, y + 0.03), (0.9, y + 0.03)], bs.BLUE, 1.8)
        self.label_row(cv, eng, 1.0, y, ['compression: Pr', ('live', prc), 'kip, Mr', ('live', mr), 'kip-ft'], 8)
        y -= 0.2
        cv.line([(0.5, y + 0.03), (0.9, y + 0.03)], '#2C7FB8', 1.8)
        self.label_row(cv, eng, 1.0, y, ['tension: Pr,t', ('live', prt), 'kip'], 8)
        y -= 0.2
        cv.label(0.5, y, 'envelope corner at 0.9 Mr and 0.2 Pr (Eqs. 6.9.2.2.1-1 and -2 agree there)', color=bs.GREY, size=8)
        y2 = 1.0
        for (g, color), short in zip(gs, ('axial', 'combined', 'uplift')):
            cv.line([(4.1, y2 + 0.03), (4.45, y2 + 0.03)], color, 1.8)
            self.label_row(cv, eng, 4.55, y2, [short + ': Pu', ('live', f'{R}.P_u_{g + 1}/(1 kip)'), 'kip'], 8)
            y2 -= 0.2

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


# ----------------------------------------------------------------------------- formula rules
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
        if re.search(r'/\s*(in|ft|kip|ksi|ksf|klf|psf|psi|deg|lbf)\b',
                     re.sub(r'\d+(\.\d+)? [a-z]+(\^\d+)?(\*[a-z]+(\^\d+)?)*/[a-z]+(\^\d+)?', '', stripped)):
            raise BuildError(f'bare-unit division in {formula!r}')
        if re.search(r'\*\s*(in|ft|kip|ksi|ksf|klf|psf|psi|deg|lbf)\b', re.sub(r'\d+(\.\d+)? [a-z]+(\^\d+)?(\*[a-z]+(\^\d+)?)+', '', stripped)):
            raise BuildError(f'bare-unit multiplication in {formula!r}')
        for fn in re.findall(r'([A-Za-z_][A-Za-z_0-9]*)\(', stripped):
            if fn not in FUNCTION_NAMES:
                raise BuildError(f'function {fn} in {formula!r}')
    for p in rep.iter('paragraph'):
        if p.text and ('\n' in p.text or '\r' in p.text):
            raise BuildError('newline in paragraph text')


def split_list(text):
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


# ----------------------------------------------------------------------------- comparison with the notebook and the Mathcad sheet
def to_u(pm, q):
    U = pm._dsl().U
    if isinstance(q, bs.Q):
        return U(q.v, (q.d[0], q.d[1]))
    return q


def adapter_env(sheet, eng, pm):
    """An environment shaped like the Mathcad one, filled from the Blockpad evaluation."""
    env = {}
    for mc, bp in sheet.scalar_map.items():
        env[mc] = to_u(pm, eng.get(bp))
    for mc, names in sheet.vector_map.items():
        if sheet.family[mc] == 'nv':
            env[mc] = {(0, k): to_u(pm, eng.get(n)) for k, n in enumerate(names)}
        else:
            env[mc] = [to_u(pm, eng.get(n)) for n in names]
    return env


def close(a, b, tol=TOL):
    return abs(a - b) <= tol * max(abs(b), 1e-6)


def notebook_comparisons(sheet, env, e, pm):
    """(label, Blockpad value, notebook value) for every quantity both hold; returns (list, approximations)."""
    d = pm._dsl()
    out = []
    names = [x['name'] for x in e.definitions] + list(e.external_meta)
    missing = [n for n in names if n not in env]
    if missing:
        raise BuildError(f'notebook quantities missing from the Blockpad sheet: {sorted(missing)}')
    for n in names:
        unit = e.units.get(n)
        out.append((n, d._to(env[n], pm._u(unit)), float(e.value(n, unit))))
    # inputs
    for spec in INPUT_SPEC:
        value = e.case['inputs'].get(spec['name'])
        if spec['family'] not in (e.family, 'both') or value is None:
            continue
        if spec['name'] not in env:
            raise BuildError(f'input {spec["name"]} is missing from the Blockpad sheet')
        unit = pm._u(spec['unit'])
        out.append((f'input {spec["name"]}', d._to(env[spec['name']], unit) if unit else env[spec['name']].v, float(value)))
    # ratios
    ratio = {c.key: c.ratio for c in e.checks}
    for name, key, _ in pm.summary_checks(e):
        out.append((f'{name} vs check {key}', env[name].v, float(ratio[key])))
    numeric = [env[name].v for name, _, _ in pm.summary_checks(e)]
    out.append(('DC_max', env['DC_max'].v, max(numeric)))
    # records
    for g, (key, short, rec) in enumerate(pm.demand_records(e)):
        for name, field, unit in (('P_fbmp', 'P_fbmp', 'kip'), ('M_2', 'M2', 'kip*ft'), ('M_3', 'M3', 'kip*ft'), ('M_res', 'M_res', 'kip*ft'),
                                  ('V_res', 'V_res', 'kip'), ('P_u', 'P_u', 'kip')):
            out.append((f'{name}[{g}] {short}', d._to(env[name][g], pm._u(unit)), float(rec[field])))
    approx = []
    if e.family == 'psc':
        curve = e.curve
        n_str = len(env['x_st'])
        out.append(('P_n_pt', d._to(env['P_n_pt'], 'kip'), float(curve['Pn'][-1])))
        out.append(('P_r_pt', d._to(env['P_r_pt'], 'kip'), float(curve['Pr'][-1])))
        out.append(('P_r_pc', d._to(env['P_r_pc'], 'kip'), float(curve['Pr'][0])))
        mine = sorted((round(env['y_st'][s].v, 6), round(env['x_st'][s].v, 6)) for s in range(n_str))
        theirs = sorted((round(y, 6), round(x, 6)) for x, y in e.details['layout'])
        if len(mine) != len(theirs):
            raise BuildError('strand count differs from the notebook layout')
        for k, ((ym, xm), (yt, xt)) in enumerate(zip(mine, theirs)):
            out.append((f'strand {k} y', ym, yt))
            out.append((f'strand {k} x', xm, xt))
        for geo, cv in (('x', curve), ('r', curve['resultant'])):
            out.append((f'd_t_{geo}', d._to(env[f'd_t_{geo}'], 'in'), float(cv['d_t'])))
        out.append(('DC_ray', env['DC_ray'].v, float(e.details['ratio_rs'])))
        out.append(('tan alpha_rs', env['tan_rs'].v, env['r_rs'].v))
        out.append(('tan alpha_sh', env['tan_sh'].v, env['r_sh'].v))
        out.append(('DC_bi vs 5.6.4.5', env['DC_bi'].v, float(e.details['biaxial']['ratio'])))
        import numpy as np
        exact = sections.psc_interaction(e.details['section'], c_values=np.array([d._to(env['c_gov'], 'in')]),
                                         angle=math.radians(e.value('alpha_rs', 'deg')), phi_c=e.case['inputs']['phi_c'],
                                         phi_t=e.case['inputs']['phi_t'])
        for key, name, unit in (('Pn', 'P_n_cg', 'kip'), ('Mn', 'M_n_cg', 'kip*ft'), ('eps_t', 'eps_t_cg', None), ('phi', 'phi_cg', None),
                                ('Pr', 'P_r_cg', 'kip'), ('Mr', 'M_r_cg', 'kip*ft')):
            out.append((name, d._to(env[name], pm._u(unit)) if unit else env[name].v, float(exact[key][1])))
        if 'M_cap_u' in env:
            out.append(('M_cap_u', d._to(env['M_cap_u'], 'kip*ft'), float(sections.moment_capacity_at_axial(curve, e.value('P_u_bi', 'kip')))))
        approx.append(('DC at c_gov (exact) vs the interpolated resultant-axis D/C', env['DC_cg'].v, float(e.value('DC_rs')), APPROX_TOL))
    return out, approx


def data_table_comparisons(env, e):
    """The Pile Data Table entries the sheet's values produce (SDG 3.5.15.D rounding) against e.data_table."""
    header = dict(DATA_TABLE_COLUMNS)
    ceil = lambda x: int(math.ceil(x - 1e-9))
    have = bool(e.details['fdl']['FDL_record'])
    calc = {'C': ceil(env['NBR_tons'].v) if have else 'N/A', 'I': ceil(env['FDL_tons'].v) if have else 'N/A',
            'J': ceil(env['DD_tons'].v) if env['DD_tons'].v > 0 else 'N/A',
            'K': ceil(env['R_scour_total_tons'].v) if env['R_scour_total_tons'].v > 0 else 'N/A',
            'L': ceil(env['R_scour_net_tons'].v) if env['R_scour_net_tons'].v > 0 else 'N/A',
            'P': round(env['phi_geo'].v, 2), 'Q': round(env['EL_cutoff'].v / 12.0, 1)}       # lengths are inches in the evaluator
    bad = [(letter, calc[letter], e.data_table[header[letter]]) for letter in calc if calc[letter] != e.data_table[header[letter]]]
    return len(calc), bad


def compare_envs(pm, mine, theirs):
    """Compare the quantities both environments hold; returns (count, mismatches)."""
    U = pm._dsl().U
    count, bad = 0, []

    def one(label, a, b):
        nonlocal count
        if isinstance(a, U) and isinstance(b, U):
            count += 1
            if abs(a.d[0] - b.d[0]) > 1e-9 or abs(a.d[1] - b.d[1]) > 1e-9 or not close(a.v, b.v):
                bad.append((label, a, b))

    for name, a in mine.items():
        if name not in theirs:
            continue
        b = theirs[name]
        if isinstance(a, list) and isinstance(b, list):
            for i, (x, y) in enumerate(zip(a, b)):
                one(f'{name}[{i}]', x, y)
        elif isinstance(a, dict) and isinstance(b, dict):
            for key, x in a.items():
                if key in b:
                    one(f'{name}{list(key)}', x, b[key])
        else:
            one(name, a, b)
    return count, bad


def sha(data):
    return hashlib.sha256(data).hexdigest()


# ----------------------------------------------------------------------------- build
def check_stamp(rep, live):
    """The first element after the stylerules is the ProjectStamp table (multiline cells; live ProjectInfo references or static text)."""
    tables = [t for t in rep.iter('table') if t.get('name') == 'ProjectStamp']
    if len(tables) != 1:
        raise BuildError(f'the report holds {len(tables)} ProjectStamp tables, not 1')
    first = next(el for el in rep if el.tag not in ('include', 'stylerule'))
    if first.tag != 'embed' or first.find('table') is not tables[0]:
        raise BuildError('the ProjectStamp table is not the first thing after the report stylerules')
    cells = bs.stamp_cells(tables[0])
    if [v for _, v, _ in cells] != [bs.PROJECT_STAMP[k] for k in bs.STAMP_KEYS]:
        raise BuildError('the ProjectStamp values differ from PROJECT_STAMP')
    if [owner for _, _, owner in cells] != [f'{bs.PROJECT_INFO}.{k}' if live else None for k in bs.STAMP_KEYS]:
        raise BuildError('the ProjectStamp cells are ' + ('not live ProjectInfo references' if live else 'not static text'))
    if any(cell.tag != 'textcell' for row in tables[0].findall('row') for cell in row):
        raise BuildError('the ProjectStamp cells are not multiline cells')


def build_sheet(e, mathcad_compare=True, stamp='static'):
    """`stamp`: 'static' (the standalone sheet: the stamp as text), 'live' (the journal edition: Stamp_<Key> = ProjectInfo.<Key>)
    or None (no stamp)."""
    if stamp not in ('static', 'live', None):
        raise ValueError(f'stamp must be static, live or None, not {stamp!r}')
    pm = _mathcad()
    rev = pm.package_revision()
    ctx = pm.context(e, rev, None)
    blocks = pm.sheet(e, rev, None)
    report_name, title, filename = report_info(e)
    sheet = Sheet(e, ctx, blocks, report_name, title, pm, stamp)
    for blk in blocks:
        getattr(sheet, 'do_' + blk.kind)(blk)
    sheet.flush()
    if not sheet.summary_done:
        raise BuildError('the summary block was not reached')
    if sheet.pending_inputs:
        bs.note(sheet.notes, 'Inputs pending confirmation (captions carried "[pending confirmation]" in the notebook): '
                             + ', '.join(sheet.pending_inputs) + '.')
    bs.note(sheet.notes, 'A ✓ status covers only the recomputed numerical checks; it is not design acceptance. The pending items of the '
                         'notebook stay open. Recalculate in Blockpad after any input change.', size=9)
    rep = sheet.rep
    bs.rewrite_visible_text(rep, VISIBLE_RULES)
    bs.check_submission_text(rep)
    # ---- (a) the engine is built from the XML that will be written
    eng = bs.BpEngine(report=report_name)
    if stamp == 'live':                           # the journal edition reads the ProjectInfo strings
        for key, text in bs.PROJECT_STAMP.items():
            eng.add_external(f'{bs.PROJECT_INFO}.{key}', text)
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
    if re.fullmatch(r'[A-Za-z]{1,3}[0-9]+', report_name):
        raise BuildError('report name looks like a spreadsheet cell address')
    for el in rep.iter('table', 'canvas', 'textcell', 'section'):
        if el.get('name') in taken:
            raise BuildError(f'{el.tag} name {el.get("name")} is also a definition')
    names = [el.get('name') for el in rep.iter('table', 'canvas', 'textcell', 'section')]
    if len(names) != len(set(names)):
        raise BuildError('duplicate table, canvas, textcell or section name')
    for cv, fill in sheet.deferred:
        fill(eng)
    for el in rep.iter('plot'):
        xs, ys = plot_items(el.get('formula'))
        for item in xs + ys:
            v = eng.evaluate(item)
            if v is not bs.NULL and (not isinstance(v, bs.Q) or v.d != bs.NODIM):
                raise BuildError(f'plot coordinate {item!r} is not a plain number')
    n_cells = bs.write_caches(rep, eng, report_name)
    if stamp:
        check_stamp(rep, live=stamp == 'live')
    for el in rep.iter('c', 'planecontainer', 'lineardim'):
        if el.get('formula'):
            eng.evaluate(el.get('formula'))
    for el in rep.iter():
        if not isinstance(el.tag, str):
            raise BuildError('XML comment in the report')
    check_formula_rules(rep)

    # ---- (b) against the notebook
    env = adapter_env(sheet, eng, pm)
    shown, approx = notebook_comparisons(sheet, env, e, pm)
    bad = [(n, a, b) for n, a, b in shown if not close(a, b)]
    if bad:
        raise BuildError('Blockpad equations differ from the notebook:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40])
                         + (f'\n  ... {len(bad) - 40} more' if len(bad) > 40 else ''))
    loose = [(n, a, b, r) for n, a, b, r in approx if not abs(a - b) <= r * max(1.0, abs(b))]
    if loose:
        raise BuildError('Blockpad equations differ from the notebook beyond their tolerance:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b, _ in loose))
    n_table, table_bad = data_table_comparisons(env, e)
    if table_bad:
        raise BuildError(f'Blockpad values differ from the notebook Pile Data Table: {table_bad}')

    # ---- (c) against the verified Mathcad environment
    n_mathcad, mstatus = None, None
    if mathcad_compare:
        menv = pm.verify(blocks, e)
        n_mathcad, bad = compare_envs(pm, env, menv)
        if bad:
            raise BuildError('Blockpad values differ from the Mathcad sheet:\n' + '\n'.join(f'  {n}: {a!r} vs {b!r}' for n, a, b in bad[:40]))
        mstatus = 'PASS' if menv['Status'] == 'PASS' else 'FAIL'

    # ---- (d) Figure 3 and the Chk strings
    expected = [dc for dc, _, _ in sheet.checks()]
    if sheet.chart_names != expected:
        raise BuildError('Figure 3 stems do not follow the check list')
    chart_refs = []
    for el in rep.iter('plot'):
        m = re.search(r'If\((' + re.escape(report_name) + r'\.\w+) <= 1', el.get('formula'))
        if m:
            chart_refs.append(m.group(1).split('.', 1)[1])
    if chart_refs != expected:
        raise BuildError('Figure 3 stems reference different names than the check list')
    ratios = [eng.get(n).v for n in expected]
    if eng.get('DC_ymax').v < max(1.2, 1.1 * max(ratios)) - 1e-12:
        raise BuildError('DC_ymax does not reach the largest ratio')
    for dc, chk, _ in sheet.checks():
        want = '⊗ FAIL' if eng.get(dc).v > 1 else '✓ PASS'
        if eng.get(chk) != want:
            raise BuildError(f'{chk} is {eng.get(chk)!r} for ratio {eng.get(dc).v}')
    status = eng.get('Status')
    if status not in ('✓ All Checks Pass', '⊗ There are FAILURES'):
        raise BuildError(f'Status {status!r}')
    if mstatus is not None and (status == '✓ All Checks Pass') != (mstatus == 'PASS'):
        raise BuildError(f'Status {status!r} disagrees with the Mathcad Status {mstatus}')
    meta = dict(definitions=n_defs, functions=n_funcs, cells=n_cells, comparisons=len(shown) + n_table, approximations=len(approx),
                data_table=n_table, mathcad_values=n_mathcad, status=status, from_notebook=sheet.from_notebook, rev=rev)
    return sheet, eng, meta, filename


def build_outputs(e, mathcad_compare=True, stamp='static'):
    """dict(document, fragment, sidecar, verification, report_name, filename) for an Evaluation.

    `stamp='static'` is the standalone sheet (the project stamp as text); `stamp='live'` is the journal edition, whose stamp
    reads ProjectInfo (Stamp_<Key> = ProjectInfo.<Key>) and resolves only inside the project journal."""
    sheet, eng, meta, filename = build_sheet(e, mathcad_compare, stamp)
    document = bs.serialize(sheet.doc)
    fragment = bs.serialize(sheet.rep, declaration=False).rstrip()
    sidecar = {name: cv.sidecar() for name, cv in sheet.canvases.items()}
    a = e.case['analysis']
    verification = {
        'report_name': sheet.name, 'bpad_file': filename, 'support': e.case['support'], 'family': e.family,
        'package_revision': meta['rev'], 'fbmp_file': a['filename'], 'fbmp_sha256': a['sha256'],
        'definitions': meta['definitions'], 'functions': meta['functions'], 'cells_and_labels': meta['cells'],
        'tool_comparisons': meta['comparisons'], 'data_table_comparisons': meta['data_table'], 'approximate_comparisons': meta['approximations'],
        'mathcad_values_compared': meta['mathcad_values'], 'values_from_notebook': meta['from_notebook'], 'status': meta['status'],
        'stamp': stamp, 'bpad_sha256': sha(document), 'fragment_sha256': sha(fragment)}
    return dict(document=document, fragment=fragment, sidecar=sidecar, verification=verification, report_name=sheet.name, filename=filename)


def build(e, repo=None, info=None):
    """The .bpad document bytes of an Evaluation.

    `repo` is accepted for symmetry with pile_design.mathcad.build (the figures here are native canvases, so no checkout is needed).
    `info`, when given, receives the verification record and the report name."""
    out = build_outputs(e)
    if info is not None:
        info.update(verification=out['verification'], report_name=out['report_name'], filename=out['filename'], comparisons=out['verification']['tool_comparisons'])
    return out['document']
