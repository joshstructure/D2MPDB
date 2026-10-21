"""Self-contained HTML calculation report (calc_common.report over this package)."""
from calc_common.report import build_report as _build, write_report as _write
from .model import SPEC


def build_report(e, title=None):
    return _build(SPEC, e, title)


def write_report(e, path):
    return _write(SPEC, e, path)
