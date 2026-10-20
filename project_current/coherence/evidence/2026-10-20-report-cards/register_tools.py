"""D-068: move the CAP-TOOL, PILE-TOOL and BACKWALL-TOOL register rows to the notebooks that embed the report cards (idempotent).

    .venv\\Scripts\\python.exe project_current\\coherence\\evidence\\2026-10-20-report-cards\\register_tools.py

The notebooks were rebuilt (commits 18b47cb and a866e6b) to carry report_cards and each calculation's cited excerpt
pages; their calculation packages are otherwise the ones the journal session registered earlier on 20 October.
The row keeps its lf_text basis: SHA-256 of the file with CRLF normalised to LF, as tools/project_coherence.py computes it.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from adopt_reports import ROOT, REGISTER, DATE, DECISION, CARDS, register_rows, write_row  # noqa: E402

TOOLS = ('CAP-TOOL', 'PILE-TOOL', 'BACKWALL-TOOL')


def lf_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def main() -> int:
    lines, rows = register_rows()
    for tool in TOOLS:
        row = rows[tool]
        digest = lf_digest(ROOT / row['path'])
        note = (f'{DECISION} (20 October): notebook rebuilt to embed {CARDS} and the calculation\'s cited code-excerpt pages; '
                f'reports built from it carry definition and citation cards. Calculation package otherwise as registered earlier today. ')
        if row['sha256'] == digest and row['notes'].startswith(DECISION):
            print(f'{tool}: current')
            continue
        if not row['notes'].startswith(DECISION):
            row['notes'] = note + row['notes']
        row.update(sha256=digest, registered_on=DATE)
        write_row(lines, row)
        print(f'{tool}: {digest[:12]}')
    REGISTER.write_bytes('\n'.join(lines).encode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
