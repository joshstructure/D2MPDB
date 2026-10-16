"""Rebuild the B4 geometry CAD-table workbook from the geometry notebook and Mathcad runs.

    .venv\\Scripts\\python.exe scripts\\build_geometry_cad_tables.py [--no-recalc] [--output PATH]

Steps: execute the notebook model cells, write every tab as Excel formulas,
recalculate in Microsoft Excel (COM) so values are cached, then verify that
QC passes and that the cached results reproduce the notebook model.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from geometry_tables import excel_recalc, verify, workbook  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=workbook.OUTPUT)
    parser.add_argument('--no-recalc', action='store_true', help='skip Excel recalculation and verification')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    result = workbook.build(args.output)
    print(f"Wrote {result['output']} ({len(result['sheets'])} tabs), fingerprint {result['fingerprint']}, model {result['model_id']}")
    if args.no_recalc:
        print('Excel recalculation skipped: the workbook has formulas but no cached values.')
        return 0
    if not excel_recalc.excel_available():
        print('Microsoft Excel is not available for recalculation.', file=sys.stderr)
        return 2
    excel_recalc.recalculate(args.output)
    report = verify.verify(args.output)
    for line in report['lines']:
        print(line)
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
