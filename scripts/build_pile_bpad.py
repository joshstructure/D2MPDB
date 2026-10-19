"""Build the Blockpad (.bpad) editions of the three distilled pile-design worksheets (End Bent 1, End Bent 2, Pier).

A thin command line around pile_design/bpad.py, which is also what the notebook's export button calls. It walks the block list of
the Mathcad generator (pile_design/mathcad.py), translates each equation to Blockpad syntax (scripts/bpad_sheet.py) and writes one
standalone document per support with one report each. Before anything is written every definition is read back from the XML,
evaluated by the independent Blockpad-syntax evaluator (BpEngine) and compared with the pile notebook model and with the verified
Mathcad environment; the build stops on any mismatch.

    python scripts/build_pile_bpad.py                       # write pile_bpad/*.bpad, fragments/, preview/, verification.json
    python scripts/build_pile_bpad.py --skip-mathcad        # skip the comparison with the Mathcad environment
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pile_design import bpad  # noqa: E402
from pile_design.model import default_case, evaluate  # noqa: E402

SUPPORTS = ['End Bent 1', 'End Bent 2', 'Pier']
OUT_DIR = ROOT / 'pile_bpad'
PREVIEW_GITIGNORE = None                       # copied from cap_bpad/preview/.gitignore so the two folders ignore the same renderings


def evaluation(support):
    return evaluate(default_case(support))


def build_support(support, mathcad_compare=True):
    """The outputs of one support's preset case (report name, document, fragment, sidecar, verification)."""
    return bpad.build_outputs(evaluation(support), mathcad_compare=mathcad_compare)


def sidecar_text(sidecar):
    return json.dumps(sidecar, indent=1, ensure_ascii=False)


def verification_text(entries):
    return json.dumps(entries, indent=1, ensure_ascii=False, sort_keys=True)


def write_outputs(out, folder=OUT_DIR):
    folder = Path(folder)
    (folder / 'fragments').mkdir(parents=True, exist_ok=True)
    (folder / 'preview').mkdir(exist_ok=True)
    (folder / out['filename']).write_bytes(out['document'])
    (folder / 'fragments' / f'{out["report_name"]}.xml').write_bytes(out['fragment'])
    (folder / 'preview' / f'{out["report_name"]}.canvases.json').write_text(sidecar_text(out['sidecar']), encoding='utf-8', newline='\n')


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    compare_mathcad = '--skip-mathcad' not in argv
    entries = []
    for support in SUPPORTS:
        out = build_support(support, compare_mathcad)
        write_outputs(out)
        v = out['verification']
        entries.append(v)
        mine = f'; {v["mathcad_values_compared"]} values match the Mathcad sheet' if compare_mathcad else ''
        print(f'Wrote pile_bpad/{out["filename"]}: {v["definitions"]} definitions; {v["tool_comparisons"]} values match the notebook{mine}; '
              f'report {out["report_name"]}; {v["status"]}')
    ignore = ROOT / 'cap_bpad' / 'preview' / '.gitignore'
    if ignore.is_file():
        (OUT_DIR / 'preview' / '.gitignore').write_bytes(ignore.read_bytes())
    (OUT_DIR / 'verification.json').write_text(verification_text(entries), encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
