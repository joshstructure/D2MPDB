"""Write the Blockpad editions of the journal-calculation packages (standalone sheet and, with --journal, the journal edition).

    .venv\\Scripts\\python.exe scripts\\build_journal_calc_bpads.py                 # every package, standalone sheets
    .venv\\Scripts\\python.exe scripts\\build_journal_calc_bpads.py --journal       # every package, journal editions (live references)
    .venv\\Scripts\\python.exe scripts\\build_journal_calc_bpads.py fence_wind --journal journal/D2_I95_Project_Journal.bpad

Outputs per package: ``<package>/<Title>.bpad`` with ``<package>/bpad/{fragments/<Report>.xml, verification.json}``; the
journal edition goes to ``<package>/bpad/journal/`` (fragment, review copy, coherence.json, verification.json). Every
build is verified against the notebook before anything is written (calc_common/bpad.py).
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calc_common import bpad  # noqa: E402
from calc_common.notebook import embedded_revision  # noqa: E402

PACKAGES = ['wind_superstructure', 'fence_wind', 'bridge_movement', 'superstructure_uplift', 'mse_wall_exclusion', 'bearing_design']
# pier_wall_fins (C006) was sequestered on 2026-10-22 (D-082): sequestered/pier_wall_fins/, not built or tested.


def revision_of(spec):
    return embedded_revision(spec, ROOT) or 'working copy'


def build_standalone(package):
    model = importlib.import_module(f'{package}.model')
    e = model.evaluate()
    sheet, eng, meta = bpad.build(model.SPEC, e, revision=revision_of(model.SPEC))
    entry = bpad.write_outputs(model.SPEC, sheet, eng, meta)
    print(f'{package}: wrote {entry["bpad_file"]}: {entry["definitions"]} definitions; {entry["tool_comparisons"]} values match the notebook; '
          f'status {entry["status"]}')
    return entry


def build_journal(package, links):
    model = importlib.import_module(f'{package}.model')
    e = model.evaluate()
    sheet, eng, meta = bpad.build(model.SPEC, e, revision=revision_of(model.SPEC), journal=links)
    entry = bpad.write_journal_outputs(model.SPEC, links, sheet, eng, meta)
    kept = entry['literals_kept']
    print(f'{package}: {entry["journal_references"]} journal references verified, {len(kept)} literals kept; {entry["tool_comparisons"]} values match '
          f'the notebook; status {entry["status"]} -> {entry["fragment"]}')
    return entry


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    journal = '--journal' in argv
    path = ROOT / 'journal' / 'D2_I95_Project_Journal.bpad'
    if journal:
        i = argv.index('--journal')
        if i + 1 < len(argv) and not argv[i + 1].startswith('--') and argv[i + 1] not in PACKAGES:
            path = Path(argv[i + 1])
            path = path if path.is_absolute() or path.exists() else ROOT / path
    packages = [a for a in argv if a in PACKAGES] or PACKAGES
    if journal:
        from scripts import bpad_sheet as bs
        links = bs.JournalLinks.load(path)
        for package in packages:
            build_journal(package, links)
    else:
        for package in packages:
            build_standalone(package)
    return 0


if __name__ == '__main__':
    sys.exit(main())
