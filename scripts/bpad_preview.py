#!/usr/bin/env python3
"""Independent HTML preview for Blockpad ``.bpad`` calculation files.

What this is
------------
A reviewer-oriented renderer.  Blockpad saves an XML document
(``<document version="1.9">`` holding ``<report>`` pages).  This script reads that
XML with lxml and writes one self-contained HTML file per report (plus an
``index.html``) that shows headings, paragraphs, equations with their *cached*
results, input highlighting, colored tables, collapsed sections, links and native
canvas drawings as inline SVG.  ``--png`` additionally screenshots each page in
~1400 px chunks with headless Edge so the pages can be viewed as images.

What this is not
----------------
* It is NOT Blockpad.  Nothing is recalculated: equation results, table cells and
  label values are the ones cached in the file.  Layout, fonts and pagination are
  approximations (a report is one continuous 816 px page).
* Live canvas plots (``PlotLines`` lists that contain variables) are drawn from a
  sidecar ``<ReportName>.canvases.json`` when one exists (the builder's resolved
  geometry).  Without a sidecar, a small best-effort evaluator re-evaluates those
  formulas from the cached variable values in the file (rounded display values,
  so positions are approximate); anything it cannot evaluate is skipped and
  counted in a gray note at the bottom of the canvas.

Sidecar conventions (``--sidecar`` or ``<bpad dir>/preview/<Report>.canvases.json``)
    Coordinates are inches, y UP.  ``text`` items: (x, y) is the baseline start
    (optional ``anchor``/``rotate``).  ``dim`` items: (x1,y1)-(x2,y2) is the
    dimension line itself and (tx, ty) is the CENTER of its label.  ``line``
    items may carry ``closed``, ``fill`` and ``dash``.

Usage
-----
    bpad_preview.py <file.bpad> [--out DIR] [--sidecar PATH] [--png]
                    [--report NAME] [--expand]

Standard library + lxml only.
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree

PT = 96.0 / 72.0          # CSS px per typographic point
IN = 96.0                 # CSS px per inch
BANNER = ("Independent preview of {name} \u2014 an approximation, not a native "
          "Blockpad rendering. Values shown are the file's cached results.")
AMBER = "#F7E6B9"
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
CHUNK_PX = 1400

CSS = """
*{box-sizing:border-box}
html{background:#d9dde2}
body{margin:0;padding:0 0 40px;font-family:'Times New Roman',Times,serif;font-size:11pt;color:#111}
.banner{position:fixed;top:0;left:0;right:0;z-index:50;background:#26323d;color:#f3f5f7;
 font:12px/1.35 'Segoe UI',Arial,sans-serif;padding:6px 14px;text-align:center}
body.has-banner{padding-top:34px}
body.png .banner{position:static}
body.png.has-banner{padding-top:0}
.page{background:#fff;margin:18px auto;box-shadow:0 1px 6px rgba(0,0,0,.35);overflow:hidden}
.rhead{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid #9aa7b3;
 padding-bottom:3px;margin-bottom:10px;font-size:9pt;color:#4a5560}
.rhead .t{font-weight:bold;color:#1d2a35}
.rhead .n{font-family:Consolas,monospace;font-size:8.5pt}
p,h2,h3,h4,h5{margin:0}
p.bp{min-height:1.15em}
h2,h3,h4,h5{font-weight:bold;margin:10px 0 4px;color:#1d2a35;break-after:avoid}
h2{font-size:15pt}h3{font-size:13pt}h4{font-size:12pt}h5{font-size:11pt}
.pbreak{border-top:1px dashed #8aa0b4;margin:10px -8px 8px;height:0;position:relative}
.pbreak span{position:absolute;right:0;top:-8px;background:#fff;color:#7d8d9b;font:9px 'Segoe UI',Arial,sans-serif;padding:0 4px}
.eq{font-family:'Cambria Math','Times New Roman',serif;white-space:normal;overflow-wrap:anywhere}
.eq.input{background:%(amber)s;padding:2px 6px;border-radius:2px}
.eq .r{white-space:nowrap}
.eq .q{color:#9aa4ad;font-size:85%%}
.eq .steps{display:block;color:#5d6b77;font-size:88%%;margin-top:1px}
.vf{border:1px solid #8a97a3;border-radius:2px;padding:0 5px;background:#f7f9fb;font-size:92%%}
a{color:#1766a0}
sub,sup{line-height:0}
details.sec{margin:3px 0;border-left:3px solid #c3ced8;padding-left:8px;background:#fafbfc}
details.sec>summary{cursor:pointer;list-style:none;font:11px 'Segoe UI',Arial,sans-serif;color:#4a5b6a;padding:3px 0}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary .tw{display:inline-block;transition:transform .12s}
details.sec[open]>summary .tw{transform:rotate(90deg)}
.sec-plain{margin:0}
.embed{margin:0}
table.bt{border-collapse:collapse;table-layout:fixed;max-width:100%%;font-size:10pt}
table.bt td{padding:2px 5px;vertical-align:top;overflow-wrap:anywhere;border:0 solid transparent}
table.bt td p{margin:0}
table.bt td .fx{color:#8a949d;font-style:italic;font-size:88%%}
table.ss{font-size:9pt}
table.ss th{background:#eef1f4;border:1px solid #cfd6dc;font:10px 'Segoe UI',Arial,sans-serif;color:#667}
.canvas-title{font:11px 'Segoe UI',Arial,sans-serif;color:#667;margin:4px 0 2px}
svg.cv{display:block;background:#fff;outline:1px solid #e4e8ec;max-width:100%%;height:auto}
.cnote{font:10px 'Segoe UI',Arial,sans-serif;color:#8b95a0;margin:1px 0 4px}
.unk{color:#8a949d;font-size:9pt;font-style:italic}
.box{border:1px solid #9aa7b3;padding:4px 8px;margin:4px 0;background:#fcfcfd}
img{max-width:100%%}
.idx{max-width:820px;margin:20px auto;background:#fff;padding:24px 32px;box-shadow:0 1px 6px rgba(0,0,0,.35)}
.idx h1{font-size:18pt;margin:0 0 4px}
.idx li{margin:4px 0}
.idx .m{color:#667;font:12px 'Segoe UI',Arial,sans-serif}
""" % {"amber": AMBER}


# --------------------------------------------------------------------------- utils
def esc(s) -> str:
    return _html.escape(s or "", quote=True)


def warn(msg: str) -> None:
    print("warning: " + msg, file=sys.stderr)


def safe_name(name: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", name or "unnamed")


def truthy(v) -> bool:
    return v is not None and str(v).strip().lower() not in ("", "false", "0", "no", "off")


def fnum(s, default=None):
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return default


def parse_len(s, default_unit="pt") -> float:
    """'12' / '9pt' / '0.25 in' / '8mm' -> CSS px."""
    if s is None:
        return 0.0
    m = re.match(r"\s*(-?[\d.]+)\s*([A-Za-z]*)", str(s))
    if not m:
        return 0.0
    v = float(m.group(1))
    u = (m.group(2) or default_unit).lower()
    return v * {"pt": PT, "in": IN, "px": 1.0, "cm": IN / 2.54, "mm": IN / 25.4}.get(u, PT)


def num_list(s, n=3):
    """'1.5, 2, 0' -> [1.5, 2.0, 0.0]"""
    out = []
    for part in re.split(r"[,;]", s or ""):
        v = fnum(part)
        if v is None:
            return None
        out.append(v)
    return out if len(out) >= 2 else None


def fmt_quantity(text: str) -> str:
    """Round a cached '<num>' such as '0.9298954582985353 in' for display."""
    t = (text or "").strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(.*)", t)
    if not m:
        return t
    v = float(m.group(1))
    unit = m.group(2)
    if v == 0:
        s = "0"
    elif abs(v) < 0.01:
        s = f"{v:.3g}"
    else:
        s = f"{v:.3f}".rstrip("0").rstrip(".")
    return f"{s} {unit}".strip()


def text_of(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def is_elem(el) -> bool:
    return isinstance(el.tag, str)


# ----------------------------------------------------------------------- evaluator
class Evaluator:
    """Tiny best-effort evaluator for plot-list formulas.

    Variable values come from the file's own cached ``expresult`` text (or from
    literal assignments).  Lengths are held in inches, angles in radians.
    """

    UNITS = {"in": 1.0, "ft": 12.0, "yd": 36.0, "mm": 1 / 25.4, "cm": 1 / 2.54,
             "m": 39.37007874015748, "deg": math.pi / 180.0, "rad": 1.0}
    FUNCS = {
        "If": lambda c, a, b=None: a if c else b,
        "Or": lambda *a: any(a), "And": lambda *a: all(a), "Not": lambda a: not a,
        "Min": lambda *a: min(a[0]) if len(a) == 1 else min(a),
        "Max": lambda *a: max(a[0]) if len(a) == 1 else max(a),
        "Abs": abs, "Sqrt": math.sqrt, "Sin": math.sin, "Cos": math.cos, "Tan": math.tan,
        "Asin": math.asin, "Acos": math.acos, "Atan": math.atan, "Atan2": math.atan2,
        "Round": lambda a, n=0: round(a, int(n)), "Floor": math.floor, "Ceil": math.ceil,
        "Sign": lambda a: (a > 0) - (a < 0), "Sq": lambda a: a * a,
    }
    TOKEN = re.compile(r"""
        (?P<str>"[^"]*")
       |(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)(?:\s*(?P<unit>ft|in|yd|mm|cm|deg|rad|m)\b(?![\w.(]))?
       |(?P<id>[^\W\d][\w.]*)
       |(?P<op><=|>=|==|!=|<>|&&|\|\||[-+*/^(),<>\[\]!=])
       |(?P<ws>\s+)""", re.X)

    def __init__(self):
        self.vars: dict[str, object] = {}

    # -- values from cached display text
    @classmethod
    def parse_quantity(cls, s: str):
        s = (s or "").replace("\xa0", " ").strip()
        if s in ("True", "False"):
            return s == "True"
        comp = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*([A-Za-z\u00b0]+)?")
        pos, total, n = 0, 0.0, 0
        while pos < len(s):
            m = comp.match(s, pos)
            if not m:
                return s if s and not re.match(r"[-\d.\[{]", s) else None
            f = cls.UNITS.get((m.group(2) or "").replace("\u00b0", "deg"), 1.0)
            total += abs(float(m.group(1))) * f
            n += 1
            pos = m.end()
            while pos < len(s) and s[pos] == " ":
                pos += 1
        if not n:
            return None
        return -total if s.startswith("-") else total

    def translate(self, expr: str, scope: str) -> str:
        expr = re.sub(r"\s+to\s+(?:in|ft|yd|mm|cm|m|deg|rad)\b", "", expr)
        toks = []
        pos = 0
        while pos < len(expr):
            m = self.TOKEN.match(expr, pos)
            if not m:
                raise ValueError(f"cannot tokenize {expr[pos:pos + 12]!r}")
            pos = m.end()
            if m.lastgroup == "ws":
                continue
            toks.append(m)
        out = []
        for i, m in enumerate(toks):
            g = m.lastgroup
            if m.group("unit") is not None or g == "unit":
                g = "num"
            if g == "str":
                out.append(repr(m.group("str")[1:-1]))
            elif g == "num":
                num = m.group("num")
                u = m.group("unit")
                out.append(f"({num}*{self.UNITS[u]!r})" if u else num)
            elif g == "id":
                name = m.group("id")
                nxt = toks[i + 1].group(0) if i + 1 < len(toks) else ""
                low = name.lower()
                if nxt == "(":
                    if name not in self.FUNCS:
                        raise ValueError(f"unknown function {name}")
                    out.append(f"_F[{name!r}]")
                elif low == "null":
                    out.append("None")
                elif low in ("true", "false"):
                    out.append("True" if low == "true" else "False")
                elif low == "pi":
                    out.append(repr(math.pi))
                else:
                    key = name if "." in name else f"{scope}.{name}"
                    out.append(f"_V({key!r})")
            else:
                op = m.group("op")
                out.append({"^": "**", "<>": "!=", "&&": " and ", "||": " or ", "!": " not ",
                            "=": "=="}.get(op, op))
        return "".join(out)

    def evaluate(self, expr: str, scope: str):
        code = self.translate(expr, scope)

        def lookup(key):
            return self.vars[key]
        return eval(code, {"__builtins__": {}}, {"_F": self.FUNCS, "_V": lookup})

    # -- building the variable table from the document
    def load(self, root) -> None:
        pending = []
        for rep in root.iter("report"):
            scope = rep.get("name") or ""
            for d in rep.iter("dynexp"):
                f = d.get("formula") or ""
                m = re.match(r"\s*([^\W\d][\w.]*)\s*=(?!=)\s*(.+)$", f, re.S)
                if not m:
                    continue
                key = f"{scope}.{m.group(1)}"
                if key in self.vars:
                    continue
                res = d.find("expresult")
                val = self.parse_quantity(res.text.strip().lstrip("=").strip()) \
                    if res is not None and res.text else None
                if val is not None:
                    self.vars[key] = val
                else:
                    pending.append((key, scope, m.group(2)))
        for _ in range(8):
            left = []
            for key, scope, rhs in pending:
                try:
                    self.vars[key] = self.evaluate(rhs, scope)
                except Exception:
                    left.append((key, scope, rhs))
            if len(left) == len(pending):
                break
            pending = left

    def eval_list(self, items: list[str], scope: str):
        """Evaluate list entries; returns (values, error_count).  null/failed -> None."""
        out, errors = [], 0
        for it in items:
            it = it.strip()
            try:
                v = self.evaluate(it, scope)
                out.append(float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None)
            except Exception:
                out.append(None)
                errors += 1
        return out, errors


def split_top(s: str) -> list[str]:
    """Split on commas that are not nested in ()/[] or quotes."""
    parts, depth, cur, inq = [], 0, [], False
    for ch in s:
        if ch == '"':
            inq = not inq
        if not inq:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(cur))
                cur = []
                continue
        cur.append(ch)
    if cur or parts:
        parts.append("".join(cur))
    return parts


def parse_plotlines(formula: str):
    """'PlotLines([x...],[y...])' -> (xs, ys) raw entry strings, or None."""
    m = re.match(r"\s*PlotLines\s*\((.*)\)\s*$", formula or "", re.S)
    if not m:
        return None
    args = split_top(m.group(1))
    if len(args) != 2:
        return None
    lists = []
    for a in args:
        a = a.strip()
        if not (a.startswith("[") and a.endswith("]")):
            return None
        lists.append(split_top(a[1:-1]))
    return lists[0], lists[1]


NUM_LIT = re.compile(r"\s*(?:null|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*$")


# --------------------------------------------------------------------------- context
class Ctx:
    def __init__(self, root, fname: str, expand=False):
        self.root = root
        self.fname = fname
        self.expand = expand
        self.unknown: dict[str, int] = {}
        self.report = ""
        self.report_names = {r.get("name") for r in root.iter("report") if r.get("name")}
        self.resources = {}
        for r in root.findall("resource"):
            if r.get("name") and r.text:
                self.resources[r.get("name")] = (r.get("type") or "image/png", re.sub(r"\s+", "", r.text))
        self.cond_rules: list[tuple[str, str]] = []
        self.base_cell: dict[str, str] = {}
        self.highlight = {"Required Input": AMBER}
        self.result_only = {"result only"}
        self.sidecar: dict = {}
        self.evaluator = Evaluator()
        self.evaluator.load(root)
        self._stash = None
        self.collect_rules(root)

    def collect_rules(self, parent) -> None:
        for r in parent.findall("stylerule"):
            typ = (r.get("type") or "")
            name = r.get("name") or ""
            if typ == "AnyTableCell" and truthy(r.get("applytoall")) or typ == "AnyTableCell":
                cond = r.get("condition")
                if cond is not None:
                    c = cond.strip()
                    if len(c) >= 2 and c[0] == c[-1] == '"':
                        c = c[1:-1]
                    if r.get("background"):
                        self.cond_rules.append((c, r.get("background")))
                else:
                    for k in ("fontfamily", "fontsize", "fontweight", "horzalign", "vertalign", "textcolor", "background"):
                        if r.get(k):
                            self.base_cell[k] = r.get(k)
            if name and r.get("texthighlight"):
                self.highlight[name] = r.get("texthighlight")
            if name and "result only" in name.lower():
                self.result_only.add(name.lower())

    def note_unknown(self, tag: str) -> None:
        if tag not in self.unknown:
            warn(f"unknown element <{tag}> rendered as plain text")
        self.unknown[tag] = self.unknown.get(tag, 0) + 1

    def anchor(self, name: str) -> str:
        return f"{self.report}.{name}" if self.report else name


# --------------------------------------------------------------------------- styles
def text_css(el) -> list[str]:
    css = []
    ff = el.get("fontfamily")
    if ff:
        css.append(f"font-family:'{ff}',serif")
    fs = fnum(el.get("fontsize"))
    if fs:
        css.append(f"font-size:{fs * PT:.2f}px")
    if (el.get("fontweight") or "").lower() == "bold":
        css.append("font-weight:bold")
    if (el.get("fontstyle") or "").lower() == "italic":
        css.append("font-style:italic")
    if truthy(el.get("fontunderline")) or (el.get("textdecoration") or "").lower() == "underline":
        css.append("text-decoration:underline")
    if el.get("textcolor"):
        css.append(f"color:{el.get('textcolor')}")
    if el.get("texthighlight"):
        css.append(f"background:{el.get('texthighlight')}")
    return css


def style_attr(css: list[str]) -> str:
    return f' style="{esc(";".join(css))}"' if css else ""


# ------------------------------------------------------------------------- inline
def resolve_link(ctx: Ctx, addr: str) -> tuple[str, bool]:
    """Return (href, external)."""
    addr = (addr or "").strip()
    if addr.startswith("#"):
        target, _, ident = addr[1:].partition(";")
        rep, _, sec = target.partition(".")
        page = ""
        if rep in ctx.report_names and rep != ctx.report:
            page = safe_name(rep) + ".html"
        elif rep not in ctx.report_names and rep:
            return "#" + (ident or target), False
        frag = ident if ident else (f"{rep}.{sec}" if sec else rep)
        return f"{page}#{frag}", False
    return addr, bool(re.match(r"[a-z]+://", addr, re.I))


def render_image(ctx: Ctx, el) -> str:
    res = ctx.resources.get(el.get("source") or "")
    if not res:
        return f'<span class="unk">[image {esc(el.get("source"))}]</span>'
    w, h = fnum(el.get("width")), fnum(el.get("height"))
    size = (f' width="{w:.0f}"' if w else "") + (f' height="{h:.0f}"' if h else "")
    return f'<img src="data:{esc(res[0])};base64,{res[1]}"{size} alt="">'


MATH_TOKEN = re.compile(r"(?P<id>[^\W\d][\w.]*)|(?P<sup>\^\s*-?\d+(?:\.\d+)?)")
SUB_ID = re.compile(r"([^\W\d_]\w*?)((?:_[^\W_]\w*?)+)$")


def mathify(text: str) -> str:
    """Escape text; render name_sub identifiers as subscripts and ^n as superscripts.

    Dotted (report-scoped) names such as ``Basis.Width`` and anything inside
    quotes are left exactly as typed.
    """
    out = []
    for part in re.split(r'("[^"]*")', text):
        if part.startswith('"'):
            out.append(esc(part))
            continue
        pos = 0
        for m in MATH_TOKEN.finditer(part):
            out.append(esc(part[pos:m.start()]))
            tok = m.group(0)
            if m.group("sup"):
                out.append(f"<sup>{esc(tok[1:].strip())}</sup>")
            else:
                sm = SUB_ID.match(tok) if "." not in tok else None
                if sm:
                    out.append(f"{esc(sm.group(1))}<sub>{esc(sm.group(2)[1:])}</sub>")
                else:
                    out.append(esc(tok))
            pos = m.end()
        out.append(esc(part[pos:]))
    return "".join(out)


def is_literal_rhs(formula: str) -> bool:
    m = re.match(r"[^=]*=\s*(.+)$", formula, re.S)
    if not m:
        return False
    rhs = m.group(1).strip()
    return bool(re.fullmatch(
        r'[-+]?(?:\d[\d.,]*|\.\d+)(?:\s*[A-Za-z\u00b0/*^\d.\s-]*)?|"[^"]*"|true|false|null',
        rhs, re.I))


def render_dynexp(ctx: Ctx, el) -> str:
    formula = (el.get("formula") or "").strip()
    body_el = el.find("expbody")
    body = re.sub(r"\s+", " ", "".join(body_el.itertext())).strip() if body_el is not None else ""
    body = body or formula
    res_el = el.find("expresult")
    res = re.sub(r"\s+", " ", (res_el.text or "").replace("\xa0", " ")).strip() if res_el is not None else None
    style = el.get("style") or ""
    show_res = (el.get("showresult") or "True") != "False"
    show_form = (el.get("showformula") or "True") != "False"
    show_id = (el.get("showidentifier") or "True") != "False"
    result_only = style.lower() in ctx.result_only or (not show_form and not show_id)
    is_def = bool(re.match(r"\s*[^\W\d][\w.]*\s*\([^)]*\)\s*=(?!=)", formula))

    cls = ["eq"]
    css: list[str] = []
    hl = ctx.highlight.get(style)
    if hl:
        cls.append("input")
        css.append(f"background:{hl}")
    parts = []
    if is_def:
        parts.append(mathify(body))
    elif result_only:
        if res is not None:
            parts.append(f'<span class="r">{esc(res.lstrip("= ").strip() if res.startswith("=") else res)}</span>')
        else:
            parts.append(mathify(body) + ' <span class="q">= ?</span>')
    else:
        shown = body
        if not show_form and show_id and "=" in body:
            shown = body.split("=", 1)[0].strip()
        parts.append(mathify(shown))
        if show_res:
            if res is not None:
                parts.append(f' <span class="r">{esc(res if res.startswith("=") else "= " + res)}</span>')
            elif not is_literal_rhs(formula) and "=" in formula.replace("==", ""):
                parts.append(' <span class="q">= ?</span>')
            elif "=" not in formula.replace("==", ""):
                parts.append(' <span class="q">= ?</span>')
    steps = el.findall("expstep") if truthy(el.get("showsteps")) else []
    for st in steps:
        parts.append(f'<span class="steps">{mathify(text_of(st))}</span>')
    return f'<span class="{" ".join(cls)}"{style_attr(css)} title="{esc(formula)}">{"".join(parts)}</span>'


def render_valuefield(ctx: Ctx, el) -> str:
    val = ""
    for tag in ("textvalue", "bool", "num"):
        c = el.find(tag)
        if c is not None:
            val = fmt_quantity(c.text) if tag == "num" else (c.text or "")
            break
    return f'<span class="vf" title="{esc(el.get("name") or "")}">{esc(val)}</span>'


def inline_child(ctx: Ctx, ch) -> str:
    t = ch.tag
    if t == "span":
        return f"<span{style_attr(text_css(ch))}>{inline(ctx, ch)}</span>"
    if t == "break":
        return ('<span style="display:inline-block;width:2em"></span>'
                if (ch.get("type") or "") == "tab" else "<br>")
    if t == "link":
        href, ext = resolve_link(ctx, ch.get("address"))
        tgt = ' target="_blank" rel="noopener"' if ext else ""
        return f'<a href="{esc(href)}"{tgt}>{inline(ctx, ch)}</a>'
    if t == "dynexp":
        return render_dynexp(ctx, ch)
    if t == "valuefield":
        return render_valuefield(ctx, ch)
    if t == "image":
        return render_image(ctx, ch)
    if t == "paragraphlabel":
        return esc(text_of(ch)) + " "
    ctx.note_unknown(t)
    return f'<span class="unk">{esc(text_of(ch))}</span>'


def inline(ctx: Ctx, el) -> str:
    out = [esc(el.text)]
    for ch in el:
        if is_elem(ch):
            out.append(inline_child(ctx, ch))
        out.append(esc(ch.tail))
    return "".join(out)


# --------------------------------------------------------------------------- blocks
def render_paragraph(ctx: Ctx, el) -> str:
    css = text_css({k: v for k, v in el.attrib.items() if k != "texthighlight"})
    sb, sa = fnum(el.get("spacingbefore")), fnum(el.get("spacingafter"))
    if sb:
        css.append(f"margin-top:{sb * PT:.1f}px")
    if sa:
        css.append(f"margin-bottom:{sa * PT:.1f}px")
    if el.get("background"):
        css.append(f"background:{el.get('background')}")
    pad = fnum(el.get("level"), 0) * 24 + parse_len(el.get("leftindent"))
    if pad:
        css.append(f"padding-left:{pad:.0f}px")
    if (el.get("horzalign") or "").lower() == "center":
        css.append("text-align:center")
    elif (el.get("horzalign") or "").lower() == "right":
        css.append("text-align:right")
    inner = inline(ctx, el)
    if el.get("texthighlight"):
        inner = f'<span style="background:{esc(el.get("texthighlight"))}">{inner}</span>'
    if not inner.strip():
        inner = "&nbsp;"
    pid = f' id="{esc(el.get("id"))}"' if el.get("id") else ""
    pb = ""
    if truthy(el.get("pagebreakbefore")):
        pb = '<div class="pbreak"><span>page break</span></div>'
    return f'{pb}<p class="bp"{pid}{style_attr(css)}>{inner}</p>'


def render_heading(ctx: Ctx, el) -> str:
    lvl = int(fnum(el.get("level"), 0) or 0)
    tag = f"h{min(5, max(2, 2 + lvl))}"
    hid = f' id="{esc(el.get("id"))}"' if el.get("id") else ""
    return f"<{tag}{hid}>{inline(ctx, el)}</{tag}>"


def render_section(ctx: Ctx, el) -> str:
    name = el.get("name") or "section"
    sid = esc(ctx.anchor(name))
    inner = blocks(ctx, el)
    if (el.get("hide") or "").lower() == "true":
        n = sum(1 for _ in el.iter("dynexp"))
        op = " open" if ctx.expand else ""
        return (f'<details class="sec" id="{sid}"{op}><summary><span class="tw">\u25b8</span> {esc(name)} '
                f'(collapsed in Blockpad: {n} definitions)</summary>{inner}</details>')
    return f'<div class="sec-plain" id="{sid}">{inner}</div>'


def render_embed(ctx: Ctx, el) -> str:
    css = []
    sb, sa = fnum(el.get("spacingbefore")), fnum(el.get("spacingafter"))
    if sb:
        css.append(f"margin-top:{sb * PT:.1f}px")
    if sa:
        css.append(f"margin-bottom:{sa * PT:.1f}px")
    return f'<div class="embed"{style_attr(css)}>{blocks(ctx, el)}</div>'


def render_box(ctx: Ctx, el) -> str:
    """rectangle / textbox / float container: boxed content."""
    inner = blocks(ctx, el)
    if not inner.strip():
        return ""
    return f'<div class="box">{inner}</div>'


def render_unknown_block(ctx: Ctx, el) -> str:
    ctx.note_unknown(el.tag)
    txt = text_of(el)
    return f'<p class="unk" title="&lt;{esc(el.tag)}&gt;">{esc(txt) if txt else "&nbsp;"}</p>'


IGNORED = {"include", "stylerule", "xref", "resource"}


def render_block(ctx: Ctx, el) -> str:
    t = el.tag
    if t in IGNORED:
        return ""
    fn = {"paragraph": render_paragraph, "heading": render_heading, "section": render_section,
          "embed": render_embed, "table": render_table, "canvas": render_canvas,
          "rectangle": render_box, "textbox": render_box, "float": render_box}.get(t)
    if fn:
        return fn(ctx, el)
    if t == "dynexp":
        return f'<p class="bp">{render_dynexp(ctx, el)}</p>'
    if t == "image":
        return f'<p class="bp">{render_image(ctx, el)}</p>'
    return render_unknown_block(ctx, el)


def blocks(ctx: Ctx, parent) -> str:
    return "".join(render_block(ctx, ch) for ch in parent if is_elem(ch))


# ---------------------------------------------------------------------------- tables
def col_index(letters: str) -> int:
    n = 0
    for ch in letters.upper():
        n = n * 26 + ord(ch) - 64
    return n


def col_letters(i: int) -> str:
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_range(rng: str):
    m = re.fullmatch(r"\s*([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?\s*", rng or "")
    if not m:
        return None
    c0, r0 = col_index(m.group(1)), int(m.group(2))
    c1, r1 = (col_index(m.group(3)), int(m.group(4))) if m.group(3) else (c0, r0)
    return min(r0, r1), min(c0, c1), max(r0, r1), max(c0, c1)


BORDER_RE = re.compile(r'Border\(\s*"(\w+)"\s*,\s*"(\w+)"\s*,\s*([\d.]+)\s*,\s*"(#[0-9A-Fa-f]{3,8})"\s*\)')


def parse_colwidths(s: str) -> dict[int, float]:
    out = {}
    for m in re.finditer(r"(\d+)\s*:\s*([\d.]+)", s or ""):
        out[int(m.group(1))] = float(m.group(2))
    return out


def apply_rule_attrs(style: dict, rule) -> None:
    for k in ("background", "fontweight", "fontsize", "fontfamily", "horzalign", "vertalign",
              "textcolor", "fontstyle"):
        if rule.get(k):
            style[k] = rule.get(k)


def table_cell_css(style: dict) -> list[str]:
    css = []
    if style.get("background"):
        css.append(f"background:{style['background']}")
    if style.get("fontweight", "").lower() == "bold":
        css.append("font-weight:bold")
    if style.get("fontstyle", "").lower() == "italic":
        css.append("font-style:italic")
    if style.get("fontsize"):
        fs = fnum(style["fontsize"])
        if fs:
            css.append(f"font-size:{fs * PT:.2f}px")
    if style.get("fontfamily"):
        css.append(f"font-family:'{style['fontfamily']}',serif")
    if style.get("textcolor"):
        css.append(f"color:{style['textcolor']}")
    ha = (style.get("horzalign") or "").lower()
    if ha in ("left", "center", "right"):
        css.append(f"text-align:{ha}")
    va = (style.get("vertalign") or "").lower()
    if va in ("top", "center", "bottom"):
        css.append("vertical-align:" + {"center": "middle"}.get(va, va))
    for side in ("top", "right", "bottom", "left"):
        if style.get("b_" + side):
            css.append(f"border-{side}:{style['b_' + side]}")
    return css


def apply_borders(style: dict, border_attr: str, r, c, rng) -> None:
    r0, c0, r1, c1 = rng
    for kind, pat, w, color in BORDER_RE.findall(border_attr or ""):
        b = f"{max(float(w), 0.5):g}px {'dashed' if pat.lower().startswith('dash') else 'dotted' if pat.lower().startswith('dot') else 'solid'} {color}"
        if kind == "AllSides":
            if r == r0:
                style["b_top"] = b
            if r == r1:
                style["b_bottom"] = b
            if c == c0:
                style["b_left"] = b
            if c == c1:
                style["b_right"] = b
        elif kind == "BetweenRows" and r > r0:
            style["b_top"] = b
        elif kind == "BetweenColumns" and c > c0:
            style["b_left"] = b
        elif kind == "AllLines":
            style.update({"b_top": b, "b_bottom": b, "b_left": b, "b_right": b})


def cell_content(ctx: Ctx, cell) -> tuple[str, str]:
    """(html, displayed_text) for a <c>, <cell> or <textcell>."""
    if cell.tag == "textcell":
        return blocks(ctx, cell), text_of(cell)
    if cell.tag == "cell":
        return "", ""
    for tag in ("textvalue", "num", "bool"):
        v = cell.find(tag)
        if v is not None:
            txt = fmt_quantity(v.text) if tag == "num" else (v.text or "")
            return esc(txt).replace("\n", "<br>"), txt.strip()
    f = cell.get("formula")
    if f:
        return f'<span class="fx">{esc(f)}</span>', ""
    return "", ""


def render_grid(ctx: Ctx, rows, colwidths: dict, rules, table_class="bt", letters=False,
                default_w=100.0, name_attrs="") -> str:
    cells = [[c for c in row if is_elem(c) and c.tag in ("c", "cell", "textcell")] for row in rows]
    ncols = max((len(r) for r in cells), default=0)
    if not ncols:
        return ""
    widths = [colwidths.get(i + 1, default_w) for i in range(ncols)]
    total = sum(widths)
    parsed = []
    for rule in rules:
        rng = parse_range(rule.get("range")) if rule.get("range") else None
        if rng or truthy(rule.get("applytoall")):
            parsed.append((rule, rng or (1, 1, len(cells), ncols)))
    out = [f'<table class="{table_class}" {name_attrs} style="width:{total:.0f}px">']
    out.append("<colgroup>" + "".join(f'<col style="width:{w:.0f}px">' for w in widths) + "</colgroup>")
    if letters:
        out.append("<tr>" + '<th style="width:30px"></th>' * 0 +
                   "".join(f"<th>{col_letters(i + 1)}</th>" for i in range(ncols)) + "</tr>")
    for ri, row in enumerate(cells, 1):
        out.append("<tr>")
        for ci, cell in enumerate(row, 1):
            style = dict(ctx.base_cell)
            for rule, rng in parsed:
                r0, c0, r1, c1 = rng
                if r0 <= ri <= r1 and c0 <= ci <= c1:
                    apply_rule_attrs(style, rule)
                    apply_borders(style, rule.get("border"), ri, ci, rng)
            apply_rule_attrs(style, cell)
            inner, shown = cell_content(ctx, cell)
            if cell.tag == "c":
                for cond, bg in ctx.cond_rules:
                    if shown == cond:
                        style["background"] = bg
            out.append(f"<td{style_attr(table_cell_css(style))}>{inner}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def render_table(ctx: Ctx, el) -> str:
    name = el.get("name") or ""
    tid = f' id="{esc(ctx.anchor(name))}"' if name else ""
    grid = render_grid(ctx, el.findall("row"), parse_colwidths(el.get("colwidths")),
                       el.findall("stylerule"), name_attrs=tid.strip())
    return grid


def render_spreadsheet_page(ctx: Ctx, el) -> str:
    rows = list(el.iter("row"))
    grid = render_grid(ctx, rows, parse_colwidths(el.get("colwidths")), el.findall("stylerule"),
                       table_class="bt ss", letters=True, default_w=70.0)
    return grid or '<p class="unk">(empty spreadsheet)</p>'


# --------------------------------------------------------------------------- canvases
class Svg:
    """Inch-based, y-up drawing surface that emits SVG elements."""

    def __init__(self, w_in: float, h_in: float):
        self.w, self.h = w_in * IN, h_in * IN
        self.parts: list[str] = []

    def X(self, x):
        return x * IN

    def Y(self, y):
        return self.h - y * IN

    def polyline(self, pts, color="#000", width=1.0, dash=None, fill=None, closed=False):
        if len(pts) < 2:
            return
        p = " ".join(f"{self.X(x):.2f},{self.Y(y):.2f}" for x, y in pts)
        tag = "polygon" if closed else "polyline"
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<{tag} points="{p}" fill="{fill or "none"}" stroke="{esc(color)}" '
            f'stroke-width="{width:g}" stroke-linejoin="round" stroke-linecap="round"{d}/>')

    def circle(self, cx, cy, r, fill=None, stroke="#000", width=1.0):
        self.parts.append(
            f'<circle cx="{self.X(cx):.2f}" cy="{self.Y(cy):.2f}" r="{r * IN:.2f}" '
            f'fill="{esc(fill) if fill else "none"}" stroke="{esc(stroke) if stroke else "none"}" '
            f'stroke-width="{width:g}"/>')

    def text(self, x, y, txt, color="#000", size_pt=10.0, bold=False, anchor="start", rotate=0.0,
             italic=False, family="Times New Roman", middle=False):
        px, py = self.X(x), self.Y(y)
        tr = f' transform="rotate({-rotate:g} {px:.2f} {py:.2f})"' if rotate else ""
        w = ' font-weight="bold"' if bold else ""
        it = ' font-style="italic"' if italic else ""
        db = ' dominant-baseline="central"' if middle else ""
        lines = str(txt).split("\n")
        if len(lines) == 1:
            body = esc(lines[0])
        else:
            body = "".join(f'<tspan x="{px:.2f}" dy="{0 if i == 0 else 1.2:g}em">{esc(l)}</tspan>'
                           for i, l in enumerate(lines))
        self.parts.append(
            f'<text x="{px:.2f}" y="{py:.2f}" fill="{esc(color)}" font-size="{size_pt * PT:.2f}" '
            f'font-family="\'{esc(family)}\',Times,serif" text-anchor="{anchor}"{w}{it}{db}{tr}>{body}</text>')

    def dim_line(self, p1, p2, color="#000", width=1.0, ext=None):
        """Dimension line p1-p2 with end ticks; ext = extension line pairs [(a, b), ...]."""
        for a, b in ext or []:
            self.polyline([a, b], color, max(0.5, width * 0.6))
        (x1, y1), (x2, y2) = p1, p2
        self.polyline([p1, p2], color, width)
        L = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        t = 0.045
        for (x, y) in (p1, p2):
            self.polyline([(x - (ux - uy) * t, y - (uy + ux) * t), (x + (ux - uy) * t, y + (uy + ux) * t)],
                          color, width)

    def render(self, extra="") -> str:
        return (f'<svg class="cv" xmlns="http://www.w3.org/2000/svg" width="{self.w:.0f}" height="{self.h:.0f}" '
                f'viewBox="0 0 {self.w:.2f} {self.h:.2f}"{extra}>' + "".join(self.parts) + "</svg>")


def parse_size(s: str, default=(6.5, 4.0)):
    vals = []
    for part in (s or "").split(";"):
        m = re.match(r"\s*([\d.]+)\s*(in|ft|cm|mm|pt|px)?", part)
        if m:
            u = m.group(2) or "in"
            vals.append(float(m.group(1)) * parse_len("1" + u) / IN)
    return (vals[0], vals[1]) if len(vals) >= 2 else default


def point(s):
    v = num_list(s)
    return (v[0], v[1]) if v else None


def dash_for(pattern: str | None):
    p = (pattern or "").lower()
    return {"dash": "6 4", "dot": "1.5 3", "dashdot": "6 3 1.5 3", "dashed": "6 4", "dotted": "1.5 3"}.get(p)


def draw_sidecar(svg: Svg, items: list[dict]) -> None:
    for it in items:
        t = it.get("type")
        try:
            if t == "line":
                svg.polyline([tuple(p) for p in it["points"]], it.get("color", "#000"),
                             float(it.get("width", 1.0)), dash_for(it.get("dash")),
                             fill=it.get("fill"), closed=bool(it.get("closed")))
            elif t == "circle":
                svg.circle(it["cx"], it["cy"], it["r"], it.get("fill"), it.get("stroke", "#000"),
                           float(it.get("width", 1.0)))
            elif t == "text":
                svg.text(it["x"], it["y"], it["text"], it.get("color", "#000"), float(it.get("size", 10)),
                         bool(it.get("bold")), it.get("anchor", "start"), float(it.get("rotate", 0)),
                         bool(it.get("italic")))
            elif t == "dim":
                col = it.get("color", "#000")
                p1, p2 = (it["x1"], it["y1"]), (it["x2"], it["y2"])
                svg.dim_line(p1, p2, col, float(it.get("width", 1.0)))
                ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0]))
                if ang > 90 or ang < -90:
                    ang += 180
                svg.text(it["tx"], it["ty"], it["text"], col, float(it.get("size", 9)),
                         anchor="middle", rotate=ang if abs(ang) > 0.5 else 0, middle=True)
            else:
                warn(f"sidecar item type {t!r} ignored")
        except (KeyError, TypeError, ValueError) as e:
            warn(f"bad sidecar item {it!r}: {e}")


def lineardim_svg(svg: Svg, el) -> None:
    s, e, p = point(el.get("startpoint")), point(el.get("endpoint")), point(el.get("pointondimline"))
    if not (s and e):
        return
    color = el.get("linecolor") or "#1766A0"
    tcolor = el.get("textcolor") or color
    width = fnum(el.get("linethickness"), 1.0)
    dx, dy = e[0] - s[0], e[1] - s[1]
    L = math.hypot(dx, dy) or 1.0
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    off = ((p[0] - s[0]) * nx + (p[1] - s[1]) * ny) if p else 0.0
    a = (s[0] + nx * off, s[1] + ny * off)
    b = (e[0] + nx * off, e[1] + ny * off)
    ext = [(s, a), (e, b)] if abs(off) > 0.03 else []
    svg.dim_line(a, b, color, width, ext)
    numel = el.find("num")
    txt = fmt_quantity(numel.text) if numel is not None and numel.text else (el.get("formula") or "")
    fs = fnum(el.get("fontsize"), 9.0)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    if ang > 90 or ang < -90:
        ang += 180
    side = 1 if off >= 0 else -1
    gap = 0.07
    svg.text(mx + nx * gap * side * 1.0, my + ny * gap * side, txt, tcolor, fs, anchor="middle",
             rotate=ang if abs(ang) > 0.5 else 0, middle=True)


def render_canvas(ctx: Ctx, el) -> str:
    name = el.get("name") or ""
    w, h = parse_size(el.get("size"))
    sc = ctx.sidecar.get(name)
    title = el.get("title") or ""
    note = ""
    if sc:
        w = float(sc.get("width_in", w))
        h = float(sc.get("height_in", h))
        title = sc.get("title", title)
        svg = Svg(w, h)
        draw_sidecar(svg, sc.get("items", []))
    else:
        svg = Svg(w, h)
        live_ok = live_fail = 0
        for ch in el:
            if not is_elem(ch):
                continue
            t = ch.tag
            if t == "plot":
                r = draw_plot(ctx, svg, ch)
                live_ok += r == "live"
                live_fail += r == "skip"
            elif t == "planecontainer":
                draw_label(svg, ch)
            elif t == "circle":
                c = point(ch.get("center"))
                r = fnum(ch.get("radius"))
                if c and r is not None:
                    svg.circle(c[0], c[1], r, ch.get("fillcolor"), ch.get("linecolor") or "#000",
                               fnum(ch.get("linethickness"), 1.0))
            elif t == "lineardim":
                lineardim_svg(svg, ch)
            elif t in ("line", "arrowline", "lines", "arrowlines"):
                draw_lines(svg, ch)
            elif t == "rectangle":
                draw_rect(ctx, svg, ch)
            elif t == "include":
                continue
            else:
                ctx.note_unknown(t)
        notes = []
        if live_ok:
            notes.append(f"{live_ok} live plot(s) re-evaluated from cached values (approximate)")
        if live_fail:
            notes.append(f"{live_fail} live plot(s) not drawn (no sidecar)")
        if notes:
            note = f'<div class="cnote">{esc("; ".join(notes))}</div>'
    cid = f' id="{esc(ctx.anchor(name))}"' if name else ""
    cap = f'<div class="canvas-title">{esc(title)}</div>' if title else ""
    return f'<div class="embed"{cid}>{cap}{svg.render()}{note}</div>'


def draw_plot(ctx: Ctx, svg: Svg, el) -> str:
    """Draw a <plot>; returns 'lit', 'live' (evaluated), 'skip' or 'other'."""
    parsed = parse_plotlines(el.get("formula"))
    if not parsed:
        ctx.note_unknown("plot(" + (el.get("formula") or "")[:20] + ")")
        return "other"
    xs, ys = parsed
    color = el.get("linecolor") or "#000"
    width = fnum(el.get("linethickness"), 1.0)
    literal = all(NUM_LIT.match(s) for s in xs + ys)
    if literal:
        fx = [None if s.strip() == "null" else float(s) for s in xs]
        fy = [None if s.strip() == "null" else float(s) for s in ys]
        kind = "lit"
    else:
        fx, ex = ctx.evaluator.eval_list(xs, ctx.report)
        fy, ey = ctx.evaluator.eval_list(ys, ctx.report)
        if ex + ey >= len(xs) + len(ys):      # nothing evaluated at all
            return "skip"
        kind = "live"                          # all-null (e.g. clipped wall) is a valid empty result
    seg: list[tuple[float, float]] = []
    segs = []
    for a, b in zip(fx, fy):
        if a is None or b is None or not (math.isfinite(a) and math.isfinite(b)):
            segs.append(seg)
            seg = []
        else:
            seg.append((a, b))
    segs.append(seg)
    for s in segs:
        if len(s) >= 2:
            svg.polyline(s, color, width, dash_for(el.get("linepattern")))
        elif len(s) == 1:
            svg.circle(s[0][0], s[0][1], 0.01, color, color, 0.5)
    return kind


def draw_label(svg: Svg, el) -> None:
    o = point(el.get("origin"))
    if not o:
        return
    color = el.get("textcolor") or "#000"
    size = fnum(el.get("fontsize"), 10.0)
    txt, gray = None, False
    tv, nm = el.find("textvalue"), el.find("num")
    if tv is not None:
        txt = tv.text or ""
    elif nm is not None:
        txt = fmt_quantity(nm.text)
    elif el.get("formula"):
        txt, gray = el.get("formula"), True
    if txt is None:
        return
    d = num_list(el.get("dir")) or [1, 0, 0]
    ang = math.degrees(math.atan2(d[1], d[0])) if len(d) > 1 else 0.0
    svg.text(o[0], o[1], txt, "#8a949d" if gray else color, min(size, 7.5) if gray else size, rotate=ang,
             family=el.get("fontfamily") or "Times New Roman", italic=gray)


def parse_points(s: str):
    pts = []
    for chunk in (s or "").split(";"):
        v = num_list(chunk)
        if v:
            pts.append((v[0], v[1]))
    return pts


def draw_lines(svg: Svg, el) -> None:
    pts = parse_points(el.get("pts"))
    if not pts:
        a, b = point(el.get("startpoint")), point(el.get("endpoint"))
        pts = [a, b] if a and b else []
    if len(pts) < 2:
        return
    color = el.get("linecolor") or "#000"
    width = fnum(el.get("linethickness"), 1.0)
    svg.polyline(pts, color, width, dash_for(el.get("linepattern")))
    if el.tag.startswith("arrow") and el.get("endarrow"):
        al = (num_list(el.get("endarrow")) or [6, 3])
        L, Wd = al[0] / IN, al[1] / IN
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        d = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / d, (y2 - y1) / d
        bx, by = x2 - ux * L, y2 - uy * L
        svg.polyline([(x2, y2), (bx - uy * Wd, by + ux * Wd), (bx + uy * Wd, by - ux * Wd)],
                     color, 0.5, fill=color, closed=True)


def draw_rect(ctx: Ctx, svg: Svg, el) -> None:
    o = num_list(el.get("origin"))
    d = num_list(el.get("dir"))
    ht = fnum(el.get("height"))
    if not (o and d and ht):
        return
    w = math.hypot(d[0], d[1])
    ux, uy = (d[0] / w, d[1] / w) if w else (1.0, 0.0)
    ox, oy = o[0], o[1]
    pts = [(ox, oy), (ox + d[0], oy + d[1]), (ox + d[0] - uy * ht, oy + d[1] + ux * ht),
           (ox - uy * ht, oy + ux * ht)]
    fill = el.get("fillcolor") if (el.get("shapetype") or "").lower() == "fill" else None
    svg.polyline(pts, el.get("linecolor") or "#9aa7b3", 0.6, fill=fill or "none", closed=True)
    tb = el.find("textbox")
    if tb is not None:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, y0, x1, y1 = svg.X(min(xs)), svg.Y(max(ys)), svg.X(max(xs)), svg.Y(min(ys))
        inner = blocks(ctx, tb)
        svg.parts.append(
            f'<foreignObject x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml" style="font-size:9pt;overflow:hidden">{inner}</div>'
            "</foreignObject>")


# ---------------------------------------------------------------------------- pages
def page_doc(title: str, body: str, ctx: Ctx, extra_css="", png=False) -> str:
    cls = "has-banner" + (" png" if png else "")
    banner = f'<div class="banner">{esc(BANNER.format(name=ctx.fname))}</div>'
    return ("<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{esc(title)}</title><style>{CSS}{extra_css}</style></head>"
            f'<body class="{cls}"><div id="all">{banner}{body}</div></body></html>')


def render_report(ctx: Ctx, rep) -> str:
    saved = (list(ctx.cond_rules), dict(ctx.base_cell), dict(ctx.highlight), set(ctx.result_only))
    ctx.report = rep.get("name") or ""
    ctx.collect_rules(rep)
    ps = num_list(rep.get("pagesize")) or [816, 1056]
    mg = num_list(rep.get("margin")) or [48, 48, 48, 48]
    mg = (mg + mg)[:4] if len(mg) < 4 else mg
    title = rep.get("title") or ctx.report
    head = (f'<div class="rhead"><span class="t">{esc(title)}</span>'
            f'<span class="n">{esc(ctx.report)}</span></div>')
    content = blocks(ctx, rep)
    ctx.cond_rules, ctx.base_cell, ctx.highlight, ctx.result_only = saved
    page = (f'<div class="page" id="{esc(ctx.report)}" style="width:{ps[0]:.0f}px;padding:{mg[1]:.0f}px '
            f'{mg[2]:.0f}px {mg[3]:.0f}px {mg[0]:.0f}px"><div id="content">{head}{content}</div></div>')
    return page


def render_spreadsheet(ctx: Ctx, sh) -> str:
    ctx.report = sh.get("name") or ""
    title = sh.get("title") or ctx.report
    head = (f'<div class="rhead"><span class="t">{esc(title)}</span>'
            f'<span class="n">{esc(ctx.report)} (spreadsheet)</span></div>')
    grid = render_spreadsheet_page(ctx, sh)
    return (f'<div class="page" id="{esc(ctx.report)}" style="width:816px;padding:48px">'
            f'<div id="content">{head}<div style="overflow-x:auto">{grid}</div></div></div>')


def load_sidecar(path: Path | None):
    if not path or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as e:
        warn(f"cannot read sidecar {path}: {e}")
        return {}


def find_sidecar(explicit: Path | None, bpad: Path, outdir: Path, name: str):
    if explicit:
        p = explicit / f"{name}.canvases.json" if explicit.is_dir() else explicit
        return p
    for base in (bpad.parent / "preview", outdir):
        p = base / f"{name}.canvases.json"
        if p.is_file():
            return p
    return None


# ------------------------------------------------------------------------------ PNG
def find_edge() -> str | None:
    for p in EDGE_PATHS:
        if Path(p).is_file():
            return p
    return shutil.which("msedge")


def run_edge(edge: str, args: list[str], timeout=90):
    return subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", *args],
                          capture_output=True, text=True, timeout=timeout, encoding="utf-8",
                          errors="replace")


MEASURE_JS = """<script>window.addEventListener('load',function(){
var out=[];(function walk(el){for(var i=0;i<el.children.length;i++){var ch=el.children[i];
if(ch.classList.contains('sec-plain')||(ch.tagName==='DETAILS'&&ch.open)){walk(ch);}else{var r=ch.getBoundingClientRect();
out.push([r.top+window.scrollY,r.bottom+window.scrollY]);}}})(document.getElementById('content'));
var d=document.createElement('pre');d.id='__m';
d.textContent=JSON.stringify({blocks:out,total:document.documentElement.scrollHeight});
document.body.appendChild(d);});</script>"""


def make_pngs(html_path: Path, html_text: str, outdir: Path, report: str) -> list[Path]:
    edge = find_edge()
    if not edge:
        warn("Microsoft Edge not found; skipping --png")
        return []
    tmp = Path(tempfile.mkdtemp(prefix="bpad_png_"))
    try:
        # re-render in png mode (static banner), then measure block boxes
        mhtml = tmp / "measure.html"
        mhtml.write_text(html_text.replace("</body>", MEASURE_JS + "</body>"), encoding="utf-8")
        r = run_edge(edge, ["--window-size=900,1200", "--virtual-time-budget=4000", "--dump-dom",
                            mhtml.as_uri()])
        m = re.search(r'<pre id="__m">(.*?)</pre>', r.stdout or "", re.S)
        if not m:
            warn("could not measure page for PNG chunking; skipping")
            return []
        info = json.loads(_html.unescape(m.group(1)))
        total = int(math.ceil(info["total"]))
        chunks, start, last_bottom = [], 0.0, 0.0
        first_on_chunk = True
        for top, bottom in info["blocks"]:
            if not first_on_chunk and bottom - start > CHUNK_PX:
                chunks.append((start, last_bottom))
                start = top
                first_on_chunk = True
            first_on_chunk = False
            last_bottom = max(last_bottom, bottom)
        chunks.append((start, float(total)))
        outs = []
        for i, (y0, y1) in enumerate(chunks, 1):
            h = int(math.ceil(y1 - y0)) + 4
            cp = tmp / f"chunk{i:02d}.html"
            cp.write_text(html_text.replace("</style>", f"#all{{margin-top:-{y0:.1f}px}}</style>", 1),
                          encoding="utf-8")
            out = outdir / f"{safe_name(report)}-p{i:02d}.png"
            run_edge(edge, [f"--window-size=900,{h}", f"--screenshot={out}", cp.as_uri()])
            if out.is_file():
                outs.append(out)
        return outs
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        warn(f"PNG generation failed: {e}")
        return []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------ main
def write_index(ctx: Ctx, entries, outdir: Path) -> Path:
    items = []
    for name, title, kind, href, pngs in entries:
        links = " ".join(f'<a href="{esc(p.name)}">{esc(p.name)}</a>' for p in pngs)
        items.append(f'<li><a href="{esc(href)}">{esc(title)}</a> <span class="m">&mdash; {esc(name)}'
                     f'{" (spreadsheet)" if kind == "spreadsheet" else ""}'
                     f'{" &middot; PNG: " + links if links else ""}</span></li>')
    unk = ""
    if ctx.unknown:
        unk = ('<p class="m">Unrecognised elements (rendered as plain text): '
               + esc(", ".join(f"{t} \u00d7{n}" for t, n in sorted(ctx.unknown.items()))) + "</p>")
    body = (f'<div class="idx"><h1>{esc(ctx.fname)}</h1><p class="m">Preview index &mdash; '
            f'{len(entries)} page(s)</p><ul>{"".join(items)}</ul>{unk}</div>')
    p = outdir / "index.html"
    p.write_text(page_doc(f"Preview of {ctx.fname}", body, ctx), encoding="utf-8")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="Independent HTML preview of a Blockpad .bpad file.")
    ap.add_argument("bpad", type=Path)
    ap.add_argument("--out", type=Path, help="output directory (default: <bpad dir>/preview)")
    ap.add_argument("--sidecar", type=Path, help="canvases.json (or a directory of <Report>.canvases.json)")
    ap.add_argument("--png", action="store_true", help="also write page-chunk PNGs via headless Edge")
    ap.add_argument("--report", help="render only the report/spreadsheet with this name")
    ap.add_argument("--expand", action="store_true", help="open collapsed sections (HTML and PNG)")
    a = ap.parse_args(argv)

    if not a.bpad.is_file():
        print(f"error: file not found: {a.bpad}", file=sys.stderr)
        return 2
    try:
        root = etree.parse(str(a.bpad), etree.XMLParser(huge_tree=True)).getroot()
    except etree.XMLSyntaxError as e:
        print(f"error: {a.bpad.name} is not well-formed XML: {e}", file=sys.stderr)
        return 2
    if root.tag != "document":
        print(f"error: {a.bpad.name}: root element is <{root.tag}>, expected <document>", file=sys.stderr)
        return 2

    outdir = a.out or (a.bpad.parent / "preview")
    outdir.mkdir(parents=True, exist_ok=True)
    ctx = Ctx(root, a.bpad.name, expand=a.expand)

    entries = []
    for el in root:
        if not is_elem(el) or el.tag not in ("report", "spreadsheet"):
            if is_elem(el) and el.tag not in ("include", "stylerule", "xref", "resource", "drawing"):
                ctx.note_unknown(el.tag)
            continue
        name = el.get("name") or el.tag
        if a.report and name != a.report:
            continue
        sc_path = find_sidecar(a.sidecar, a.bpad, outdir, name)
        ctx.sidecar = load_sidecar(sc_path)
        title = el.get("title") or name
        body = render_report(ctx, el) if el.tag == "report" else render_spreadsheet(ctx, el)
        fname = safe_name(name) + ".html"
        page = page_doc(f"{title} \u2014 {name}", body, ctx)
        (outdir / fname).write_text(page, encoding="utf-8")
        pngs = []
        if a.png:
            png_html = page_doc(f"{title} \u2014 {name}", body, ctx, png=True)
            pngs = make_pngs(outdir / fname, png_html, outdir, name)
        entries.append((name, title, el.tag, fname, pngs))
        print(f"wrote {outdir / fname}" + (f" (sidecar: {sc_path})" if ctx.sidecar else "")
              + (f" + {len(pngs)} PNG" if pngs else ""))
    if a.report and not entries:
        print(f"error: no report or spreadsheet named {a.report!r}", file=sys.stderr)
        return 2
    idx = write_index(ctx, entries, outdir)
    print(f"wrote {idx}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
