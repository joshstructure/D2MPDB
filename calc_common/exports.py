"""Case, register, report and distilled Blockpad exports of a journal calculation (the backwall export set)."""
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import zipfile

from .model import upgrade_case

BPAD_VERIFICATION_SUFFIX = '_bpad_verification.json'


class Exports:
    def __init__(self, spec):
        self.spec = spec
        p = spec.prefix
        self.CASE, self.CHECKS, self.REPORT = f'{p}_case.json', f'{p}_checks.csv', f'{p}_calculation_report.html'
        self.DISTILLED_BPAD = spec.bpad_file
        self.BPAD_VERIFICATION = f'{p}{BPAD_VERIFICATION_SUFFIX}'
        self.BUNDLE = f'{p}_bundle.zip'
        self._distilled = []
        self.WRITERS = {
            self.CASE: lambda e: self.case_json(e.case).encode('utf-8'),
            self.CHECKS: lambda e: self.checks_csv(e).encode('utf-8'),
            self.REPORT: self._report,
            self.DISTILLED_BPAD: lambda e: self.distilled_bpad(e)[0],
            self.BPAD_VERIFICATION: lambda e: self.distilled_bpad(e)[1],
        }

    @staticmethod
    def case_json(case):
        return json.dumps(case, indent=1, sort_keys=False, ensure_ascii=False)

    def load_case(self, content):
        data = json.loads(bytes(content).decode('utf-8-sig'))
        return upgrade_case(self.spec, data)

    @staticmethod
    def checks_rows(e):
        for c in e.checks:
            yield dict(group=c.group, check=c.label, status=c.status, ratio='' if c.ratio is None else f'{c.ratio:.4f}',
                       demand=c.demand, capacity=c.capacity, basis=c.basis, note=c.note,
                       review='' if not c.review else f'{c.review["action"]}: {c.review["reason"]} ({c.review["utc"]})')

    def checks_csv(self, e):
        buffer = io.StringIO()
        rows = list(self.checks_rows(e))
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]) if rows else ['group', 'check', 'status'])
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()

    def _report(self, e):
        from .report import build_report
        return build_report(self.spec, e).encode('utf-8')

    def distilled_bpad(self, e):
        """(Blockpad document bytes, verification JSON bytes) of the evaluated case, built and verified in memory."""
        if self._distilled and self._distilled[0][0] is e:
            return self._distilled[0][1]
        from pier_cap.bpad_export import package_revision
        from .bpad import distill
        revision = package_revision(self.spec.dir, prefixes=(self.spec.tool_prefix,), notebooks=(self.spec.notebook,))
        result = distill(self.spec, e, revision=revision)
        self._distilled[:] = [(e, result)]
        return result

    @staticmethod
    def bpad_summary(verification):
        entry = json.loads(bytes(verification).decode('utf-8'))[0]
        return (f'{entry["tool_comparisons"]} values match the notebook to 1 part in 10⁹; distilled status {entry["status"]}; '
                f'case {entry["case_sha256"][:12]}; package {entry["package_revision"]}.')

    def _folder(self, root):
        folder = Path(root) / f'{self.spec.prefix}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}'
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def export_file(self, e, root, name):
        if name == self.BUNDLE:
            return self.export_bundle(e, root)[self.BUNDLE]
        path = self._folder(root) / name
        path.write_bytes(self.WRITERS[name](e))
        if name == self.DISTILLED_BPAD:
            (path.parent / self.BPAD_VERIFICATION).write_bytes(self.WRITERS[self.BPAD_VERIFICATION](e))
        return path

    def export_bundle(self, e, root, folder=None):
        folder = Path(folder) if folder else self._folder(root)
        folder.mkdir(parents=True, exist_ok=True)
        files = {name: writer(e) for name, writer in self.WRITERS.items()}
        for name, data in files.items():
            (folder / name).write_bytes(data)
        bundle = folder / self.BUNDLE
        with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(name, data)
        return {name: folder / name for name in files} | {self.BUNDLE: bundle}
