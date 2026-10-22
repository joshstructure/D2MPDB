"""D-080: move the CAP-TOOL, PILE-TOOL, BACKWALL-TOOL and PIER-WALL-TOOL register rows to the rebuilt notebooks (idempotent).

    .venv\\Scripts\\python.exe project_current\\coherence\\evidence\\2026-10-22-pier-cheek-walls\\register_tools.py

The pier cap cheek wall calculation (C018, pier_cheek_wall/) cites three provisions that were not yet in the code-excerpt
store (LRFD Table 3.8.1.1.2-1, LRFD 3.8.1.2.3b, LRFD 5.10.8.2.1c). Every portable notebook embeds that store
(code_excerpts/excerpts.json) for its citation cards, so the four registered notebooks were rebuilt by their own
builders with their calculation packages unchanged; only the embedded store (and so the package revision) moved.
The rows keep their lf_text basis: SHA-256 of the file with CRLF normalised to LF, as tools/project_coherence.py computes
it. source_receipt.json beside this script records the hashes written.
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
DATE, DECISION = '2026-10-22', 'D-080'
TOOLS = ('CAP-TOOL', 'PILE-TOOL', 'BACKWALL-TOOL', 'PIER-WALL-TOOL')
NOTE = (f'{DECISION} (22 October): notebook rebuilt to embed the code-excerpt store extended with the pier cheek wall citations '
        '(LRFD Table 3.8.1.1.2-1, 3.8.1.2.3b, 5.10.8.2.1c); calculation package and case handling unchanged. ')


def lf_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main() -> int:
    rows = read_rows()
    updates, receipt = {}, {}
    for tool in TOOLS:
        row = rows[tool]
        digest = lf_digest(ROOT / row['path'])
        receipt[tool] = {'path': row['path'], 'previous_sha256': row['sha256'], 'sha256': digest, 'hash_basis': row['hash_basis']}
        if row['sha256'] == digest and row['notes'].startswith(DECISION):
            print(f'{tool}: current')
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
