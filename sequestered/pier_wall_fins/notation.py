"""MathML symbols of this calculation (calc_common.notation bound to the package symbol table)."""
from calc_common.notation import Notation
from .model import SPEC

_N = Notation(SPEC)
symbol = _N.symbol
expression = _N.expression
definition_mathml = _N.definition_mathml
unit_mathml = _N.unit_mathml
