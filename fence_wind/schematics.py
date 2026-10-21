"""'What it represents' blocks (calc_common.schematics over this package)."""
from calc_common.schematics import schematic as _schematic, meaning as _meaning
from .model import SPEC


def schematic(e, name):
    return _schematic(SPEC, e, name)


def meaning(name):
    return _meaning(SPEC, name)
