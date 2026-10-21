"""Create or refresh the portable Colab notebooks of the journal-calculation packages.

    .venv\\Scripts\\python.exe scripts\\build_journal_calc_notebooks.py              # every package
    .venv\\Scripts\\python.exe scripts\\build_journal_calc_notebooks.py fence_wind   # one package

Each notebook embeds its package (`<package>/*.py`, `<package>/data/*`), `calc_common/`, the shared `pier_cap/` code, the
report cards with the cited excerpt images and the Blockpad writer (calc_common/notebook.py). Only the embedded package
and its revision change on a refresh; edited cell text is preserved. Rebuild the Blockpad editions afterwards
(scripts/build_journal_calc_bpads.py), which name the notebook revision.
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calc_common import notebook  # noqa: E402

PACKAGES = ['wind_superstructure', 'fence_wind', 'bridge_movement', 'superstructure_uplift', 'pier_wall_fins', 'mse_wall_exclusion', 'bearing_design']


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    for package in [a for a in argv if a in PACKAGES] or PACKAGES:
        spec = importlib.import_module(f'{package}.model').SPEC
        notebook.build(spec, ROOT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
