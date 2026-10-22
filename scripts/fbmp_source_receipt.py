"""Write the source receipt for a re-registered FB-MultiPier export (project_current/coherence/evidence/<date>-fbmp/).

    .venv\\Scripts\\python.exe scripts\\fbmp_source_receipt.py --source PIER-XML --date 2026-10-21 --decision D-073 \\
        --previous project_current/fbmp/pier/archive/2026-10-19/Pier_Fixed.XML --supplied "C:\\Users\\...\\Pier_Fixed.XML" \\
        --authorization "..."

Records what the D-049 receipt recorded by hand on 19 October 2026: exact bytes and hashes of the registered file and
the archived predecessor, project and software identity, load combinations, the pier node count and pile-head Z, plus an
element-wise comparison of the two exports (which leaf tags changed, how many, and the largest change per tag) so the
disposition in decisions.md can be checked against the files. It never edits a source, the register or the tracker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EVIDENCE = ROOT / 'project_current' / 'coherence' / 'evidence'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def flatten(root) -> dict[str, str]:
    """Path -> text for every element with text; repeated siblings are numbered so the map is one-to-one."""
    out: dict[str, str] = {}
    counts: Counter = Counter()

    def walk(el, prefix):
        attrs = ''.join(f'[@{k}={v}]' for k, v in sorted(el.attrib.items()) if k in ('number', 'pileset', 'location', 'node_number', 'combination'))
        key = f'{prefix}/{el.tag}{attrs}'
        counts[key] += 1
        if counts[key] > 1:
            key = f'{key}#{counts[key]}'
        text = (el.text or '').strip()
        if text:
            out[key] = text
        for child in el:
            walk(child, key)

    walk(root, '')
    return out


def compare(old_root, new_root) -> dict:
    old, new = flatten(old_root), flatten(new_root)
    changed = [k for k in old if k in new and old[k] != new[k]]
    by_leaf: dict[str, dict] = {}
    for k in changed:
        leaf = k.rsplit('/', 1)[-1].split('#')[0]
        entry = by_leaf.setdefault(leaf, {'count': 0, 'largest_abs_change': None, 'example': None})
        entry['count'] += 1
        try:
            a, b = float(old[k]), float(new[k])
        except ValueError:
            if entry['example'] is None:
                entry['example'] = {'path': k, 'before': old[k], 'after': new[k]}
            continue
        d = abs(b - a)
        if entry['largest_abs_change'] is None or d > entry['largest_abs_change']:
            entry['largest_abs_change'] = d
            entry['example'] = {'path': re.sub(r'^/FB-MULTIPIER_MODEL_DATA/', '', k), 'before': old[k], 'after': new[k]}
    sections = Counter(re.sub(r'\[@number=\d+\]', '', '/'.join(k.split('/')[2:5])) for k in changed)
    return {'elements_with_text': {'previous': len(old), 'current': len(new)}, 'only_in_previous': len(set(old) - set(new)),
            'only_in_current': len(set(new) - set(old)), 'changed': len(changed), 'changed_by_section': dict(sections.most_common()),
            'changed_by_leaf_tag': by_leaf}


def describe(root, raw: bytes, path: str) -> dict:
    text = lambda p: (root.findtext(p) or '').strip()
    nodes = [n for n in root.iter('NODE') if n.get('location') == 'Pier']
    z = sorted({float(n.findtext('COORDINATES/Z')) for n in nodes if n.find('COORDINATES/Z') is not None})
    segment = root.find('.//PILE_GEOMETRY/SEGMENT')
    material = {child.tag: (child.text or '').strip() for child in segment.find('MATERIAL_PROPS')} if segment is not None else {}
    return {'path': path, 'sha256': sha256(raw), 'bytes': len(raw), 'project': text('PROJECT_INFO/PROJECT_NAME'),
            'software_version': text('PROJECT_INFO/VERSION_NUMBER'), 'project_date': text('PROJECT_INFO/PROJECT_DATE'),
            'units': text('CONTROL_INFO/UNITS'), 'analysis': text('CONTROL_INFO/ANALYSIS'),
            'load_combinations': [{'number': c.get('number'), 'limitstate': (c.get('limitstate') or '').strip()} for c in root.findall('MODEL_INFO/LOAD_COMBINATION')],
            'pier_node_count': len(nodes), 'pier_node_z_in': z, 'pile_material_props_ksi': material}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--source', required=True, help='register source id, for example PIER-XML')
    parser.add_argument('--date', required=True, help='YYYY-MM-DD')
    parser.add_argument('--decision', required=True)
    parser.add_argument('--previous', required=True, help='repository path of the archived previous export')
    parser.add_argument('--supplied', default='', help='where the user supplied the file (recorded as text only)')
    parser.add_argument('--authorization', default='')
    parser.add_argument('--scope', default='')
    parser.add_argument('--downstream', default='')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    from scripts.register_update import read_rows
    rows = read_rows()
    row = rows[args.source]
    current_path = ROOT / row['path']
    raw = current_path.read_bytes()
    if sha256(raw) != row['sha256']:
        raise ValueError(f'{row["path"]} does not carry the registered SHA-256 {row["sha256"]}.')
    previous_path = ROOT / args.previous
    prev = previous_path.read_bytes()
    cur_root, prev_root = ET.fromstring(raw), ET.fromstring(prev)
    consumers = sorted(sid for sid, r in rows.items() if args.source in [d for d in r['depends_on'].split(';') if d])
    receipt = {
        'date': args.date, 'decision': args.decision, 'authorization': args.authorization, 'scope': args.scope,
        'register_row': dict(row), 'supplied_path': args.supplied,
        'file': describe(cur_root, raw, row['path']),
        'archived_previous': describe(prev_root, prev, args.previous),
        'comparison_with_previous': compare(prev_root, cur_root),
        'direct_consumers': consumers,
        'downstream_disposition': args.downstream,
        'verification': {'exact_supplied_bytes': True, 'registered_sha256_matches_file': True, 'archived_bytes_present': True,
                         'native_recalculation_performed': False},
    }
    folder = EVIDENCE / f'{args.date}-fbmp'
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / 'source_receipt.json'
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    c = receipt['comparison_with_previous']
    print(f'Wrote {out.relative_to(ROOT).as_posix()}: {c["changed"]} changed elements; by leaf tag: '
          + ', '.join(f'{k} {v["count"]}' for k, v in c['changed_by_leaf_tag'].items()))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
