"""Run every journal-calculation package with its journal inputs and write its export set to ``<package>/report/``.

    .venv\\Scripts\\python.exe scripts\\export_journal_calc_reports.py              # every package
    .venv\\Scripts\\python.exe scripts\\export_journal_calc_reports.py fence_wind   # one package

The export set is the notebook's: case JSON, calculation report (HTML), checks CSV, the distilled Blockpad sheet with its
verification record, and the bundle ZIP. The report folder is rewritten in place (no timestamp) so the committed report
always describes the committed package and data.
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calc_common.exports import Exports  # noqa: E402

PACKAGES = ['wind_superstructure', 'fence_wind', 'bridge_movement', 'superstructure_uplift', 'pier_wall_fins', 'mse_wall_exclusion', 'bearing_design']


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    for package in [a for a in argv if a in PACKAGES] or PACKAGES:
        model = importlib.import_module(f'{package}.model')
        e = model.evaluate()
        x = Exports(model.SPEC)
        files = x.export_bundle(e, ROOT, folder=ROOT / package / 'report')
        print(f'{package}: {e.status}; wrote ' + ', '.join(sorted(p.name for p in files.values())) + f' to {package}/report/')
    return 0


if __name__ == '__main__':
    sys.exit(main())
