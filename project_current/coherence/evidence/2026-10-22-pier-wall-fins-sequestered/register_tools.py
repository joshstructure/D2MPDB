"""D-082: move the registered tool-notebook rows to the notebooks rebuilt without the C006 citations (idempotent).

    .venv\\Scripts\\python.exe project_current\\coherence\\evidence\\2026-10-22-pier-wall-fins-sequestered\\register_tools.py

The pier wall fin-plate and hairpin calculation C006 (pier_wall_fins) was withdrawn from the project and its references
removed from code_excerpts/library.json; the code-excerpt store lost the 30 provisions only C006 cited. Every portable
notebook embeds that store (code_excerpts/excerpts.json) for its citation cards, so the registered notebooks were rebuilt
by their own builders with their calculation packages unchanged; only the embedded store (and so the package revision)
moved. The rows keep their lf_text basis: SHA-256 of the file with CRLF normalised to LF, as tools/project_coherence.py
computes it. source_receipt.json beside this script records the hashes written. CHEEK-TOOL is included when that row
exists (registered by D-081 the same day).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.register_update import read_rows, update_rows  # noqa: E402

HERE = Path(__file__).resolve().parent
DATE, DECISION = '2026-10-22', 'D-082'
TOOLS = ('CAP-TOOL', 'PILE-TOOL', 'BACKWALL-TOOL', 'PIER-WALL-TOOL', 'CHEEK-TOOL')
NOTE = (f'{DECISION} (22 October): notebook rebuilt to embed the code-excerpt store without the C006 pier wall fin-plate citations '
        '(C006 withdrawn to sequestered/; 30 provisions only it cited dropped); calculation package and case handling unchanged. ')


def lf_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main() -> int:
    rows = read_rows()
    updates, receipt = {}, {}
    for tool in TOOLS:
        row = rows.get(tool)
        if row is None:
            print(f'{tool}: not registered')
            continue
        digest = lf_digest(ROOT / row['path'])
        receipt[tool] = {'path': row['path'], 'previous_sha256': row['sha256'], 'sha256': digest, 'hash_basis': row['hash_basis']}
        if row['sha256'] == digest:
            print(f'{tool}: current' + ('' if row['notes'].startswith(DECISION) else ' (hash unchanged; row left as registered)'))
            continue
        change = {'sha256': digest, 'registered_on': DATE}
        if not row['notes'].startswith(DECISION):
            change['notes'] = NOTE
        updates[tool] = change
        print(f'{tool}: {digest[:12]}')
    if updates:
        update_rows(updates, prepend_notes=True)
    (HERE / 'source_receipt.json').write_text(json.dumps({'decision': DECISION, 'date': DATE, 'tools': receipt}, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
