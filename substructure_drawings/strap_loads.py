"""Design loads of the reinforcing straps for the Δ legend (STYLE_GUIDE D6).

The straps are designed and furnished by the proprietary wall provider; the
legend states the loads they are designed to resist.  The loads are not typed
here: ``scripts/export_strap_loads.py`` evaluates the selected backwall case
(``project_current/cap_design/backwall/selected_case.json``) and writes
``data/strap_loads.json`` (service and factored tie-back load per foot of
backwall, the governing combination, and the SHA-256 of the case it came
from).  ``tests/test_substructure_dxf.py`` compares that hash with the case
file, so a changed backwall design fails the test until the loads are
re-exported and the drawings rebuilt:

    scripts\\export_strap_loads.py then scripts\\build_substructure_dxf.py
"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent / "data" / "strap_loads.json"

_cache = {}


def load():
    """The exported strap loads (dict of ``data/strap_loads.json``), cached."""
    if "loads" not in _cache:
        _cache["loads"] = json.loads(PATH.read_text(encoding="utf-8"))
    return _cache["loads"]


def legend_text():
    """The paragraph of the Δ legend with the design loads filled in."""
    d = load()
    return ("REINFORCING STRAPS AND ATTACHMENTS FOR THE END BENT SHALL BE DESIGNED AND FURNISHED BY THE "
            "PROPRIETARY WALL PROVIDER. THE STRAPS SHALL BE DESIGNED TO RESIST A SERVICE LOAD OF %.2f K/FT AND A "
            "FACTORED LOAD OF %.2f K/FT (%s) PERPENDICULAR TO THE END BENT BACKWALL."
            % (d["service_kip_ft"], d["factored_kip_ft"], d["governing"].upper()))
