"""Definitions, case handling and checks: the shared engine over this package's data."""
from pathlib import Path

from calc_common.spec import CalcSpec
from calc_common import model as _m

SPEC = CalcSpec(Path(__file__).resolve().parent)
INPUT_SPEC = SPEC.input_spec
INPUTS = SPEC.inputs
SECTIONS = [(s["key"], s["title"]) for s in SPEC.sections]
REFERENCES = SPEC.references
SOURCES = SPEC.sources
FORMAT = SPEC.format


def default_case():
    return _m.default_case(SPEC)


def upgrade_case(case):
    return _m.upgrade_case(SPEC, case)


def validate_case(case):
    return _m.validate_case(SPEC, case)


def evaluate(case=None):
    return _m.evaluate(SPEC, case)


def formula_trace(e):
    return _m.formula_trace(e)
