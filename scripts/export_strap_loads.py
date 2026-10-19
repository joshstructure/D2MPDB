"""Write the tie-back strap loads of the selected backwall case for the
substructure sheets (STYLE_GUIDE D6: the Δ legend carries the service and
factored loads per foot of backwall, SDM 12.3.F).

    .venv\\Scripts\\python.exe scripts\\export_strap_loads.py

Reads project_current/cap_design/backwall/selected_case.json, evaluates the
end bent walls engine (end_bent_walls.model.evaluate) and writes
substructure_drawings/data/strap_loads.json with the values, the governing
combination and the SHA-256 of the case file, so the sheets and the test
know when the case changes.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from end_bent_walls.model import STRENGTH, evaluate  # noqa: E402

CASE = ROOT / "project_current" / "cap_design" / "backwall" / "selected_case.json"
OUT = ROOT / "substructure_drawings" / "data" / "strap_loads.json"


def main():
    case = json.loads(CASE.read_text(encoding="utf-8"))
    e = evaluate(case)
    governing = max(STRENGTH, key=lambda c: e.value("f_str_" + c["key"]))
    data = {
        "source": "end_bent_walls.model.evaluate on " + CASE.relative_to(ROOT).as_posix(),
        "case_sha256": hashlib.sha256(CASE.read_bytes()).hexdigest(),
        "case_name": case.get("name", ""),
        "service_kip_ft": round(e.value("f_str_s", "kip/ft"), 3),
        "factored_kip_ft": round(e.value("f_str_u", "kip/ft"), 3),
        "governing": governing["label"],
        "note": "Tie-back load per foot of backwall, perpendicular to the backwall (SDM 12.3.F plan note).",
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=1))


if __name__ == "__main__":
    main()
