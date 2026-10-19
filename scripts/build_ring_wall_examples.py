"""Reproduce checked starting-case exports without running the notebook UI."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ring_wall.model import analyze
from ring_wall.output import export_results

if __name__ == '__main__':
    result = analyze()
    paths = export_results(result, ROOT / 'ring_wall' / 'examples')
    print(result['overall'])
    for path in paths:
        print(path.relative_to(ROOT))
