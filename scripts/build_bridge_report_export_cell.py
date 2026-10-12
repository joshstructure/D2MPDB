"""Refresh the portable HTML-report exporter embedded in the geometry notebook."""
import base64
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'Bridge_Geometry_2 Beam_V2.ipynb'


def main():
    package = ROOT / 'bridge_report'
    assets = {p.name: p.read_text(encoding='utf-8') for p in package.iterdir()
              if p.is_file() and p.suffix in ('.html', '.js')}
    bundle = dict(source=(package/'__init__.py').read_text(encoding='utf-8'), assets=assets)
    encoded = base64.b64encode(zlib.compress(json.dumps(bundle).encode('utf-8'), 9)).decode('ascii')
    chunks = '\n'.join("    '" + encoded[i:i+100] + "'" for i in range(0, len(encoded), 100))
    nb = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    cell = next(c for c in nb['cells'] if c.get('id') == 'bridge-report-export')
    cell['source'] = ('''# @title Export interactive report — works offline after download
# Embedded report renderer and D3 7.9.0 (ISC license); no external runtime files needed.
# Maintained in bridge_report/; rebuild with scripts/build_bridge_report_export_cell.py.
import base64 as _report_base64
import json as _report_json
import zlib as _report_zlib
_report_bundle = _report_json.loads(_report_zlib.decompress(_report_base64.b64decode(
''' + chunks + '''
)))
_BRIDGE_REPORT_ASSETS = _report_bundle['assets']
exec(compile(_report_bundle['source'], '<bridge_interactive_report>', 'exec'), globals())
report_export = show_interactive_report_export()
''').splitlines(keepends=True)
    cell['outputs'] = []
    cell['execution_count'] = None
    NOTEBOOK.write_text(json.dumps(nb, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
    print(f'Updated {NOTEBOOK.name}: embedded renderer and {len(assets)} assets.')


if __name__ == '__main__':
    main()
