"""Jupyter / Colab interface (calc_common.widgets over this package)."""
from calc_common.widgets import CalcNotebook
from .model import SPEC


class Notebook(CalcNotebook):
    def __init__(self, case=None, export_root="exports"):
        super().__init__(SPEC, case, export_root)
