"""Update existing rows of project_current/source_register.csv in place, preserving every other byte.

    from scripts.register_update import update_rows
    update_rows({'PIER-XML': {'sha256': ..., 'registered_on': '2026-10-21', 'notes': 'D-073. ...'}}, prepend_notes=True)

A changed row needs a recorded disposition (project_current/AGENTS.md), so callers pass the decision text in
`notes`; with `prepend_notes=True` the new text is put in front of the existing notes so the history stays in
the row. Line endings, the optional BOM, the field order and all untouched rows are kept exactly. Each source id
must exist once; a missing or duplicated id raises.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / 'project_current' / 'source_register.csv'
FIELDS = ['source_id', 'topic', 'path', 'status', 'scope', 'sha256', 'registered_on', 'depends_on', 'origin', 'notes', 'hash_basis']


def read_rows(path: Path = REGISTER) -> dict[str, dict]:
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    return {row['source_id']: row for row in rows}


def update_rows(updates: dict[str, dict], prepend_notes: bool = True, path: Path = REGISTER) -> dict[str, dict]:
    """Rewrite the named rows with the given fields; return the rows as written."""
    raw = path.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    text = raw.decode('utf-8-sig')
    lines = text.splitlines(keepends=True)
    fields = next(csv.reader([lines[0]]))
    if fields != FIELDS:
        raise ValueError(f'Unexpected register header: {fields}')
    seen: dict[str, int] = {}
    for i, line in enumerate(lines[1:], 1):
        sid = next(csv.reader([line]))[0]
        seen[sid] = seen.get(sid, 0) + 1
    for sid in updates:
        if seen.get(sid, 0) != 1:
            raise ValueError(f'{sid}: expected exactly one register row, found {seen.get(sid, 0)}')
    written = {}
    for i, line in enumerate(lines[1:], 1):
        values = next(csv.reader([line]))
        row = dict(zip(fields, values))
        sid = row['source_id']
        if sid not in updates:
            continue
        change = dict(updates[sid])
        unknown = set(change) - set(FIELDS)
        if unknown:
            raise ValueError(f'{sid}: unknown fields {sorted(unknown)}')
        if prepend_notes and 'notes' in change and row['notes']:
            change['notes'] = change['notes'].rstrip() + ' ' + row['notes']
        row.update(change)
        ending = '\r\n' if line.endswith('\r\n') else '\n'
        buf = io.StringIO(newline='')
        csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator=ending).writerow([row[f] for f in fields])
        lines[i] = buf.getvalue()
        written[sid] = row
    path.write_bytes((b'\xef\xbb\xbf' if bom else b'') + ''.join(lines).encode('utf-8'))
    return written
