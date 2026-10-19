"""T013 independent check: the three changed reports differ from the T012 journal only in the provenance sentence."""
import difflib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402

candidate = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'generated' / 'T013-cap-provenance-01' / 'candidate.bpad'
base = Journal.load(TASK / 'base.bpad')
cand = Journal.load(candidate)
record = {'candidate': str(candidate), 'candidate_sha256': cand.sha256, 'base_sha256': base.sha256, 'reports': {}}
ok = True
for key in ('report:CapDesignBasis', 'report:CapDesignEndBentOne', 'report:CapDesignEndBentTwo', 'report:CapDesignPier'):
    before = base.part(key).decode('utf-8').splitlines()
    after = cand.part(key).decode('utf-8').splitlines()
    removed = [l for l in difflib.ndiff(before, after) if l.startswith('- ')]
    added = [l for l in difflib.ndiff(before, after) if l.startswith('+ ')]
    entry = {'lines_removed': len(removed), 'lines_added': len(added),
             'only_provenance': all('cap notebook package' in l for l in removed) and len(removed) == len(added)
             and all('Distilled from' in l for l in added)}
    if key == 'report:CapDesignBasis':
        entry['unchanged'] = base.part(key) == cand.part(key)
        ok &= entry['unchanged']
    else:
        ok &= entry['only_provenance'] and len(removed) == 1
    record['reports'][key] = entry
unchanged = [k for k in base.order if base.hashes[k] != cand.hashes.get(k)]
record['changed_components'] = unchanged
ok &= set(unchanged) == {'report:CapDesignEndBentOne', 'report:CapDesignEndBentTwo', 'report:CapDesignPier'}
record['passed'] = bool(ok)
(TASK / 'independent-checks.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))
sys.exit(0 if ok else 1)
