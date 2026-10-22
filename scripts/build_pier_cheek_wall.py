"""Rebuild chain of the pier cap cheek wall calculation (C018, package ``pier_cheek_wall``).

    .venv\\Scripts\\python.exe scripts\\build_pier_cheek_wall.py              # notebook, standalone Blockpad sheet, report folder
    .venv\\Scripts\\python.exe scripts\\build_pier_cheek_wall.py --journal    # also the journal edition (live C001 references)

Order: the portable notebook ``Pier_Cheek_Wall_Design.ipynb`` (calc_common/notebook.py embeds the package), then the
standalone Blockpad edition ``pier_cheek_wall/Pier Cheek Walls.bpad`` (names the notebook revision), then the export set
under ``pier_cheek_wall/report/`` (case JSON, report, checks CSV, sheet, verification record, bundle). Every sheet is
verified against the package before it is written (calc_common/bpad.py). ``tests/test_pier_cheek_wall.py`` says which
edition is stale.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calc_common import bpad, notebook  # noqa: E402
from calc_common.exports import Exports  # noqa: E402

PACKAGE = 'pier_cheek_wall'


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    from pier_cheek_wall import model
    spec = model.SPEC
    notebook.build(spec, ROOT)
    revision = notebook.embedded_revision(spec, ROOT) or 'working copy'
    e = model.evaluate()
    sheet, eng, meta = bpad.build(spec, e, revision=revision)
    entry = bpad.write_outputs(spec, sheet, eng, meta)
    print(f'{PACKAGE}: wrote {entry["bpad_file"]}: {entry["definitions"]} definitions; {entry["tool_comparisons"]} values match the notebook; '
          f'status {entry["status"]}')
    if '--journal' in argv:
        from scripts import bpad_sheet as bs
        links = bs.JournalLinks.load(ROOT / 'journal' / 'D2_I95_Project_Journal.bpad')
        sheet, eng, meta = bpad.build(spec, e, revision=revision, journal=links)
        entry = bpad.write_journal_outputs(spec, links, sheet, eng, meta)
        print(f'{PACKAGE}: {entry["journal_references"]} journal references verified; status {entry["status"]} -> {entry["fragment"]}')
    files = Exports(spec).export_bundle(e, ROOT, folder=ROOT / PACKAGE / 'report')
    print(f'{PACKAGE}: {e.status}; wrote ' + ', '.join(sorted(p.name for p in files.values())) + f' to {PACKAGE}/report/')
    return 0


if __name__ == '__main__':
    sys.exit(main())
