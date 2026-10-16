"""Read-only access to the sources behind the geometry CAD-table workbook.

* The Colab geometry notebook is the geometry authority. Its CONFIG and model
  are loaded by executing the same cells the notebook regression tests use.
* The two registered Mathcad beam runs supply saved beam-design results. Values
  are read from the worksheets' stored results; Mathcad is never recalculated.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'Bridge_Geometry_2 Beam_V2.ipynb'
ROADWAY_XML = ROOT / 'Geometry Report.xml'
MODEL_CELLS = ('bridge-02', 'bridge-03', 'bridge-05', 'bridge-06')
MATHCAD = {
    1: ROOT / 'project_current/mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span1.xmcd',
    2: ROOT / 'project_current/mathcad/PrestressedBeamV6.2_Pedestrian_2Beam_Span2.xmcd',
}
# pandas is absent from the project venv; the Codex runtime supplies it (see tests).
FALLBACK_SITE = Path(r'C:\Users\joshs\.cache\codex-runtimes\codex-primary-runtime'
                     r'\dependencies\python\Lib\site-packages')


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def notebook_text_sha256(path: Path = NOTEBOOK) -> str:
    """Same lf_text basis as the source register (line endings normalized)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


@contextlib.contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _ensure_pandas():
    try:
        import pandas  # noqa: F401
    except ImportError:
        if FALLBACK_SITE.is_dir() and str(FALLBACK_SITE) not in sys.path:
            sys.path.append(str(FALLBACK_SITE))
        import pandas  # noqa: F401


def load_notebook_model(notebook: Path = NOTEBOOK):
    """Execute the notebook's input and model cells; return (CONFIG, model, env)."""
    _ensure_pandas()
    import matplotlib
    matplotlib.use('Agg')
    document = json.loads(Path(notebook).read_text(encoding='utf-8'))
    cells = {c.get('id'): c for c in document['cells']}
    missing = [ident for ident in MODEL_CELLS if ident not in cells]
    if missing:
        raise RuntimeError(f'Geometry notebook cells not found: {missing}')
    env: dict = {}
    with _working_directory(ROOT):
        for ident in MODEL_CELLS:
            exec(''.join(cells[ident]['source']), env)
        # Keep the notebook's relative XML path so the model ID matches the
        # documented notebook model ID (the ID hashes the whole CONFIG).
        config = copy.deepcopy(env['CONFIG'])
        config['roadway']['xml_path'] = ROADWAY_XML.name
        model = env['BridgeModel'](config)
    return config, model, env


# ---------------------------------------------------------------- Mathcad --
ML = '{http://schemas.mathsoft.com/math30}'
WS = '{http://schemas.mathsoft.com/worksheet30}'
UNITS = '{http://schemas.mathsoft.com/units10}'


def _local(tag: str) -> str:
    return tag.split('}')[-1]


def _unwrap(node):
    """Mathcad wraps copied expressions in <ml:provenance>; the math is its last ML child."""
    while node is not None and _local(node.tag) == 'provenance':
        node = next((k for k in reversed(list(node)) if k.tag.startswith(ML)), None)
    return node


def _name(node) -> str:
    node = _unwrap(node)
    sub = node.get('subscript')
    text = (node.text or '').strip()
    return f'{text}.{sub}' if sub else text


def _canonical(node) -> str:
    node = _unwrap(node)
    tag = _local(node.tag)
    if tag == 'id':
        return _name(node)
    if tag in ('real', 'str'):
        return (node.text or '').strip()
    if tag == 'apply':
        kids = [k for k in node if _local(k.tag) not in ('result',)]
        if not kids:
            return '()'
        head = _local(kids[0].tag) if _local(kids[0].tag) != 'id' else _name(kids[0])
        return f"{head}({','.join(_canonical(k) for k in kids[1:])})"
    if tag == 'parens':
        return '(' + ','.join(_canonical(k) for k in node) + ')'
    return tag


def _result(node):
    """Return (value, units) from a <result>; value is float, str or list."""
    if node is None:
        return None, ()
    reals, units, strings = [], [], []
    for element in node.iter():
        tag = _local(element.tag)
        if tag == 'real':
            reals.append(float(element.text))
        elif tag == 'str':
            strings.append(element.text or '')
        elif tag == 'unitReference':
            units.append((element.get('unit'), element.get('power', '1')))
    if strings and not reals:
        return strings[0], ()
    matrix = node.find(f'.//{ML}matrix')
    if matrix is not None:
        return reals, tuple(units)
    return (reals[0] if len(reals) == 1 else reals), tuple(units)


@dataclass
class MathcadValues:
    path: Path
    defines: dict = field(default_factory=dict)   # name -> list[(value, units)]
    evals: dict = field(default_factory=dict)     # canonical expression -> list[(value, units)]

    def define(self, name: str, index: int = -1):
        rows = self.defines.get(name)
        if not rows:
            raise KeyError(f'{self.path.name}: no saved result for {name}')
        return rows[index]

    def evaluated(self, expression: str, index: int = -1):
        rows = self.evals.get(expression)
        if not rows:
            raise KeyError(f'{self.path.name}: no saved evaluation {expression}')
        return rows[index]


def read_mathcad(path: Path) -> MathcadValues:
    values = MathcadValues(Path(path))
    root = ET.parse(path).getroot()
    for math in root.iter(f'{WS}math'):
        for top in math:
            kind = _local(top.tag)
            if kind in ('define', 'globalDefine'):
                lhs = _unwrap(top[0])
                name = _name(lhs) if _local(lhs.tag) == 'id' else _canonical(lhs)
                result = top.find(f'.//{ML}result')
                if result is None:
                    result = top.find('.//{http://schemas.mathsoft.com/math30}result')
                values.defines.setdefault(name, []).append(_result(result))
            elif kind == 'eval':
                expression = next((k for k in top if _local(k.tag) not in ('result', 'unitOverride')), None)
                if expression is None:
                    continue
                result = top.find(f'{ML}result')
                values.evals.setdefault(_canonical(expression), []).append(_result(result))
    return values


def _expect(value_units, unit=None):
    value, units = value_units
    if unit is not None and units and units[0][0] != unit:
        raise ValueError(f'Unexpected Mathcad unit {units} (expected {unit}).')
    return value


def mathcad_beam_data(span: int) -> dict:
    """Saved results needed by the workbook, with their Mathcad variable names."""
    path = MATHCAD[span]
    mc = read_mathcad(path)
    zones = []
    # A1-A3 end zones, then S1-S4; the S4 count is completed by the program to midspan.
    for zone in ('A1', 'A2', 'A3', 'S1', 'S2', 'S3', 'S4'):
        spaces = mc.defines.get(f'NumberOfStirrupSpaces.{zone}')
        zones.append(dict(zone=zone, spacing_in=_expect(mc.define(f'StirrupSpacing.{zone}'), 'inch'),
                          spaces=None if not spaces else int(round(spaces[-1][0])),
                          area_in2=_expect(mc.define(f'StirrupArea.{zone}'))))
    data = dict(
        span=span,
        source_file=str(path.relative_to(ROOT)).replace('\\', '/'),
        source_sha256=sha256(path),
        input_data_file=mc.evaluated('InputDataFile')[0],
        beam_type=mc.define('BeamType')[0],
        L_beam_ft=_expect(mc.define('L.beam')),
        bearing_distance_in=_expect(mc.define('BearingDistance')),
        pad_width_in=_expect(mc.define('PadWidth')),
        beam_spacing_ft=_expect(mc.define('BeamSpacing', 0)),
        t_deck_in=_expect(mc.define('t.deck', 0)),
        h_buildup_in=_expect(mc.define('h.buildup')),
        skew_deg=_expect(mc.define('Skew')),
        fc_beam_ksi=_expect(mc.define('f.c.beam')),
        fci_beam_ksi=_expect(mc.define('f.ci.beam')),
        fc_deck_ksi=_expect(mc.define('f.c.deck')),
        Eci_ksi=_expect(mc.define('E.ci')),
        Ec_ksi=_expect(mc.define('E.c')),
        humidity_pct=_expect(mc.define('H')),
        environment=mc.define('Environment')[0],
        strand_type=mc.evaluated('StrandType')[0],
        strand_area_in2=_expect(mc.evaluated('A.strand')),
        strands=int(round(mc.define('#Strands')[0])),
        debonded=int(round(mc.evaluated('NumberOfDebondedTendons')[0])),
        jacking_kip=_expect(mc.define('JackingForce.per.strand')),
        top_strands=int(round(mc.define('NoStrands.partial.ps')[0])),
        top_strand_force_kip=_expect(mc.define('Force.strand.partial.ps')),
        top_strand_dia_in=_expect(mc.define('Dia.strand.partial.ps')),
        creep_120=_expect(mc.define('Cr.120day')),
        shrink_120=_expect(mc.define('ε.sh.120')),
        defl_release_in=_expect(mc.evaluated('max(Defl.release)')),
        defl_120_in=_expect(mc.evaluated('max(Defl.120day)')),
        defl_dl_nc_in=_expect(mc.evaluated('min(Defl.dl.nc)')),
        defl_dl_c_in=_expect(mc.evaluated('min(Defl.dl.c)')),
        net_camber_in=_expect(mc.define('NetCamber')),
        stirrup_end_space_in=_expect(mc.define('EndSpace'), 'inch'),
        stirrup_zones=zones,
    )
    return data


def roadway_segments(model) -> list[dict]:
    """Roadway segments exactly as the notebook model parsed them."""
    return [dict(row) for row in model.road]
