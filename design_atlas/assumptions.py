"""Attach the hand-edited assumptions-and-gaps register to an atlas snapshot.

The register is read as recorded. Entries are pinned to their related nodes,
counted on those nodes, and marked stale when the source register now adopts
a different revision of a basis source. Nothing here re-judges an entry.
"""
from __future__ import annotations

from tools.project_coherence import ASSUMPTIONS, read_assumptions, assumption_state, OPEN_DISPOSITIONS


def attach_assumptions(data, root, register_rows, evidence, path=ASSUMPTIONS):
    """Add data['assumptions'] and per-node badge counts; returns the summary."""
    register = read_assumptions(root / path)
    entries = []
    for entry in (register or {}).get('entries', []):
        state = assumption_state(entry, register_rows)
        record = dict(entry)
        record['node_ids'] = list(entry.get('nodes') or [])
        record['open'] = (entry.get('disposition') or {}).get('status') in OPEN_DISPOSITIONS if isinstance(entry.get('disposition'), dict) else False
        record.update(stale=state['stale'], stale_sources=state['stale_sources'],
                      unknown_sources=state['unknown_sources'], current_basis=state['current_basis'])
        record['flagged'] = record['open'] or record['stale']
        record['evidence'] = evidence(path, 'entries[id = ' + str(entry.get('id', '')) + ']', entry,
                                      'Hand-edited register entry; the recorded basis hashes are compared with the current source register at build time.')
        entries.append(record)
    # Open and stale entries come first in every listing.
    entries.sort(key=lambda e: (not e['stale'], not e['open'], str(e.get('id', ''))))
    for node in data['nodes']:
        related = [e for e in entries if node['id'] in e['node_ids']]
        node['assumption_total'] = len(related)
        node['assumption_open'] = sum(e['open'] for e in related)
        node['assumption_stale'] = sum(e['stale'] for e in related)
        node['assumption_flags'] = sum(e['flagged'] for e in related)
    summary = {'schema': (register or {}).get('schema', 'd2mpdb.assumptions-register'),
               'schema_version': (register or {}).get('schema_version', 1), 'path': path,
               'present': register is not None, 'note': (register or {}).get('note', ''),
               'entries': entries,
               'counts': {'total': len(entries), 'open': sum(e['open'] for e in entries),
                          'stale': sum(e['stale'] for e in entries), 'flagged': sum(e['flagged'] for e in entries)}}
    data['assumptions'] = summary
    data.setdefault('checks', {})['assumptions'] = summary['counts']
    return summary


def validate_assumptions(data):
    """Schema checks for the snapshot: stable ids, resolvable nodes, tracked evidence."""
    summary = data.get('assumptions') or {'entries': []}
    ids = {n['id'] for n in data['nodes']}
    seen = set()
    for entry in summary['entries']:
        key = str(entry.get('id', ''))
        if not key or key in seen: raise ValueError('Duplicate or blank assumption id ' + key)
        seen.add(key)
        for node in entry['node_ids']:
            if node not in ids: raise ValueError('Assumption ' + key + ' names unknown atlas node ' + str(node))
        if entry['evidence']['path'] not in data['documents']: raise ValueError('Untracked assumptions register evidence')
        if entry.get('unknown_sources'): raise ValueError('Assumption ' + key + ' names unregistered basis source ' + ', '.join(entry['unknown_sources']))
