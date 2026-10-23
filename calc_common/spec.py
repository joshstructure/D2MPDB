"""The calculation specification: everything a package's data folder says about one journal calculation."""
import json
import re
from pathlib import Path

PASS, FAIL = '✓ PASS', '⊗ FAIL'
ALL_PASS, FAILURES = '✓ All Checks Pass', '⊗ There are FAILURES'
SCHEMA_VERSION = 1


def bare_heading(title):
    """Section title without its number ('1.2 Wind speed and exposure' -> 'Wind speed and exposure', 'Step 2. Fence
    geometry' -> 'Fence geometry'), so an input group written as the bare heading lands in its own section."""
    return re.sub(r'^(?:Step\s+)?\d+(\.\d+)*\.?\s+', '', title, flags=re.I) if isinstance(title, str) else title


class CalcSpec:
    """Loaded once per package from ``<package>/data``; immutable after construction."""

    def __init__(self, package_dir):
        self.dir = Path(package_dir).resolve()
        self.package = self.dir.name
        data = self.dir / 'data'
        self.data_dir = data
        self.text = self._json(data / 'text.json')
        self.input_spec = self._json(data / 'inputs.json')
        self.inputs = {d['name']: d for d in self.input_spec}
        self.definition_spec = self._json(data / 'definitions.json')
        self.sections = self._json(data / 'sections.json')
        self.section_titles = {s['key']: s['title'] for s in self.sections}
        self.checks = self._json(data / 'checks.json')
        self.tables = self._json(data / 'tables.json')
        self.table_by_name = {t['name']: t for t in self.tables}
        self.references = self._json(data / 'references.json')
        self.sources = self._json(data / 'sources.json')
        blocks = data / 'journal_blocks.xml'
        self.blocks_xml = blocks.read_bytes() if blocks.is_file() else None
        self.name = self.text['report_name']                      # the journal report name (C001WindLoadOnPedBridgeSuperstructure)
        self.cnumber = self.text['cnumber']                        # C001
        self.title = self.text['title']                            # Wind Load on Ped Bridge Superstructure
        self.full_title = f'{self.cnumber} - {self.title}'
        self.prefix = self.text['prefix']                          # export file prefix (wind)
        self.bpad_file = self.text['bpad_file']                    # Superstructure Wind.bpad
        self.notebook = self.text['notebook']                      # Superstructure_Wind.ipynb
        self.tool_prefix = self.text['tool_prefix']                # extracted package folder prefix (wind-tool-)
        self.format = f'd2mpdb-{self.package.replace("_", "-")}'
        self.published = list(self.text.get('published', []))     # names other journal modules read from this report
        self.anchors = dict(self.text.get('anchors', {}))         # section key -> native anchor id kept for inbound links
        self._validate()

    @staticmethod
    def _json(path):
        return json.loads(path.read_text(encoding='utf-8'))

    def _validate(self):
        names = [d['name'] for d in self.input_spec] + [d.get('name') or d['function'].split('(')[0] for d in self.definition_spec]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            raise ValueError(f'{self.package}: duplicate names {sorted(dup)}')
        keys = set(self.section_titles)
        for d in self.definition_spec:
            if d['section'] not in keys:
                raise ValueError(f'{self.package}: definition {d.get("name")} in unknown section {d["section"]}')
        for d in self.definition_spec:
            for r in d.get('refs', []):
                if r not in self.references:
                    raise ValueError(f'{self.package}: unknown reference key {r} on {d.get("name")}')
        for c in self.checks:
            for n in c.get('names', []):
                if n not in names:
                    raise ValueError(f'{self.package}: check {c["key"]} names unknown {n}')

    # -- convenience
    def definition(self, name):
        for d in self.definition_spec:
            if d.get('name') == name:
                return d
        return None

    def section_definitions(self, key):
        return [d for d in self.definition_spec if d['section'] == key]

    def input_groups(self):
        groups = []
        for d in self.input_spec:
            if d.get('group') not in groups:
                groups.append(d.get('group'))
        return groups

    def refs_text(self, keys):
        return '; '.join(f'{self.references[k]["code"]} {self.references[k]["article"]}' for k in keys if k in self.references)
