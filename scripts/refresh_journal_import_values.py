"""Re-evaluate a package's journal-import snapshot with the current journal's referenced values.

    .venv\\Scripts\\python.exe scripts\\refresh_journal_import_values.py pier_wall_fins superstructure_uplift

``<package>/data/journal_import.json`` (scripts/import_journal_calc.py) records the former hand-authored journal module:
its definitions in document order, each with the value the journal's own formula gives when evaluated independently with
the referenced values of the other journal modules. ``tests/test_journal_calc_packages.py`` compares the package with
those values. When a journal value the module reads changes (the pier wall row of the gravity sheet under D-075), the
formulas of the former module are still the fidelity reference but their values are not: this script keeps every item
as snapshotted (formula, caption, notes, prose, canvases, links) and rewrites only ``evaluated`` of the definitions,
``externals`` (the referenced values), ``skipped`` and the journal identity, and records what changed under ``refreshed``.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import bpad_sheet as bs  # noqa: E402
from scripts.import_journal_calc import JOURNAL, evaluate_module  # noqa: E402


def refresh(package: str) -> dict:
    path = ROOT / package / 'data' / 'journal_import.json'
    raw = path.read_bytes()
    nl = '\r\n' if b'\r\n' in raw else '\n'
    snap = json.loads(raw.decode('utf-8'))
    links = bs.JournalLinks.load(JOURNAL)
    values, externals, skipped, _ = evaluate_module(snap['items'], links, snap['report'])
    changed, same = [], 0
    for it in snap['items']:
        if it.get('kind') not in ('def', 'function') or it['name'] not in values:
            continue
        new = values[it['name']]
        old = it.get('evaluated')
        if old == new:
            same += 1
        else:
            changed.append({'name': it['name'], 'before': old, 'after': new})
        it['evaluated'] = new
    ext = {}
    for q, v in externals.items():
        owner, name = q.split('.', 1)
        entry = {'kind': links.owner_kind(owner)}
        entry.update({'v': v.v, 'dims': list(v.d)} if isinstance(v, bs.Q) else {'text': v})
        prior = snap.get('externals', {}).get(q, {})
        entry.update({k: prior[k] for k in ('cache', 'journal_formula') if k in prior})
        if entry['kind'] == 'spreadsheet':
            cache, formula = links.cells(owner).get(name, (None, None))
            entry['cache'], entry['journal_formula'] = cache, formula
        ext[q] = entry
    changed_ext = sorted(q for q in ext if snap.get('externals', {}).get(q, {}).get('v') != ext[q].get('v'))
    snap['externals'] = ext
    snap['skipped'] = skipped
    sha = hashlib.sha256(JOURNAL.read_bytes()).hexdigest()
    record = {'journal_sha256': sha, 'previous_journal_sha256': snap.get('journal_sha256'),
              'definitions_changed': [c['name'] for c in changed], 'definitions_unchanged': same, 'externals_changed': changed_ext,
              'note': 'Values re-evaluated from the former module\'s own formulas with the current journal\'s referenced values '
                      '(scripts/refresh_journal_import_values.py); formulas, captions, notes and prose unchanged.'}
    refreshed = snap.setdefault('refreshed', [])
    if refreshed and refreshed[-1]['journal_sha256'] == sha:      # rerun on the same journal: replace the last record
        record['previous_journal_sha256'] = refreshed[-1]['previous_journal_sha256']
        refreshed[-1] = record
    else:
        refreshed.append(record)
    snap['journal_sha256'] = sha
    text = json.dumps(snap, indent=1, ensure_ascii=False)
    path.write_bytes((text.replace('\n', nl) + nl).encode('utf-8'))
    return {'package': package, 'changed': [c['name'] for c in changed], 'unchanged': same, 'externals_changed': changed_ext}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    for package in argv:
        print(json.dumps(refresh(package), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
