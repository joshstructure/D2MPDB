"""T013: refresh the four cap-design reports promoted by T012 from the current cap_bpad/journal fragments.

The journal edition no longer prints the cap notebook package revision in its provenance paragraph (it is tied to
its report by the case and formula hashes), so a pier_cap edit stops forcing a journal task. Rerunnable.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal  # noqa: E402

mapping = json.loads((TASK / 'components.json').read_text(encoding='utf-8-sig'))
base = Journal.load(TASK / 'base.bpad')
written = {}
for key, filename in mapping.items():
    name = key.split(':', 1)[1]
    fragment = (ROOT / 'cap_bpad' / 'journal' / f'{name}.xml').read_bytes().rstrip(b'\r\n')
    (TASK / 'components' / filename).write_bytes(fragment)
    written[key] = {'file': filename, 'changed': base.part(key) != fragment,
                    'package_revision_in_fragment': b'cap notebook package' in fragment,
                    'package_revision_in_journal': b'cap notebook package' in base.part(key)}
print(json.dumps(written, indent=2))
