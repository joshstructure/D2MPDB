"""Build the distilled Mathcad 15 worksheets of the pile designs (End Bent 1 and the Pier).

A thin command line around pile_design/mathcad.py, which is also what the notebook's export button calls. Each worksheet
is written from the preset case of its support (the registered FB-MultiPier export, the Standard Plans pattern or the pipe
section, the downdrag of the geotechnical engineer). The generator parses every expression once, evaluates it with unit
checking and compares each result with the pile notebook model before the file is written; it stops on any mismatch, on a
region that crosses a page or the right edge of the text area, and on an evaluation order Mathcad would not follow.

    python scripts/build_pile_mathcad.py                   # write pile_mathcad/*.xmcd
    python scripts/build_pile_mathcad.py --render-figures  # redraw pile_design/mathcad/*.png first (matplotlib)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pile_design import mathcad  # noqa: E402
from pile_design.model import default_case, evaluate  # noqa: E402
from scripts import mathcad_sheet  # noqa: E402

SUPPORTS = ['End Bent 1', 'Pier']
OUT_DIR = ROOT / 'pile_mathcad'


def output_name(support):
    return f'{support} Pile Design.xmcd'


def evaluation(support):
    return evaluate(default_case(support))


def build(support, info=None):
    """Worksheet XML text of one support's preset case (figures read from pile_design/mathcad)."""
    return mathcad.build(evaluation(support), repo=ROOT, info=info)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for support in SUPPORTS:
        e = evaluation(support)
        if '--render-figures' in argv:
            for path in mathcad.render_figures(e, ROOT / 'pile_design' / 'mathcad'):
                print('drew', path.relative_to(ROOT).as_posix())
        info = {}
        text = mathcad.build(e, repo=ROOT, info=info)
        (OUT_DIR / output_name(support)).write_text(text, encoding='utf-8', newline='\n')
        fills = info['page_fills']
        print(f'Wrote pile_mathcad/{output_name(support)}: {len(text) // 1024} KB; {info["comparisons"]} values match the notebook '
              f'(+{info["approximations"]} approximate); {len(fills)} pages, fullest {max(fills)} of {mathcad_sheet.PAGE_H:g} pt; '
              f'page fills {fills}')


if __name__ == '__main__':
    main()
