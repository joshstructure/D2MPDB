"""Read-only extraction of the MSE wall back-face lines from the saved FreeCAD model (T016).

Same reading as mse_strap_check/extract_layout.py (saved native WallProfile properties, no
FreeCAD run), written to tasks/T016/mse_layout_20261019.json. The bent centres are taken
from the registered 13 October 2026 snapshot (mse_strap_check/layout_snapshot.json): the
model frame and the support stations are unchanged, which this script asserts.

    .venv\\Scripts\\python.exe tasks/T016/extract_mse_layout.py [--check]
"""
import hashlib
import json
import math
import struct
import sys
import zipfile
import xml.etree.ElementTree as E
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
OUT = TASK / "mse_layout_20261019.json"
MODEL = ROOT / "project_current/geometry/freecad/B4 Pedestrian Bridge and Ramps - Pond14D - Source Update 20261010.FCStd"


def extract():
    z = zipfile.ZipFile(MODEL)
    doc = E.fromstring(z.read("Document.xml"))
    objects = {o.get("name"): {p.get("name"): p[0] for p in o.find("Properties") if p.tag == "Property"} for o in doc.find("ObjectData")}

    def scalar(obj, key):
        return float(objects[obj][key].get("value"))

    def vec(obj, key):
        return [float(objects[obj][key].get("value" + k)) for k in "XYZ"]

    def vectors(obj, key):
        b = z.read(objects[obj][key].get("file"))
        n = struct.unpack("<I", b[:4])[0]
        assert len(b) == 4 + n * 24
        return [list(struct.unpack_from("<ddd", b, 4 + 24 * i)) for i in range(n)]

    def ft(v):
        return [n / 304.8 for n in v]

    frame = objects["BridgePGL"]["Frame"]
    a = float(frame.get("A"))
    origin = [float(frame.get(k)) / 304.8 for k in ["Px", "Py"]]
    result = {"model_sha256": hashlib.sha256(MODEL.read_bytes()).hexdigest(), "frame_angle_deg": math.degrees(a), "frame_origin_ft": origin,
              "wall_thickness_ft": scalar("MSEInputs", "WallThickness") / 304.8, "pad_width_ft": scalar("MSEInputs", "FootingWidth") / 304.8,
              "EndCapLength_in": scalar("BridgePGL", "EndCapLength") / 25.4, "EndCapWidth_in": scalar("BridgePGL", "EndCapWidth") / 25.4,
              "EndPileSpacing_in": scalar("BridgePGL", "EndPileSpacing") / 25.4, "EndPileSize_in": scalar("BridgePGL", "EndPileSize") / 25.4,
              "walls": {}}
    for name in objects:
        if name.startswith("Wall") and name.endswith("Profile"):
            start = ft(vec(name, "Start"))
            t = vec(name, "Tangent")
            n = vec(name, "Normal")
            bc = vectors(name, "BaseControls")
            length = max(p[0] for p in bc) / 304.8
            result["walls"][name[4:-7]] = {"start": start[:2], "end": [start[i] + t[i] * length for i in range(2)],
                                           "tangent": t[:2], "outward": n[:2], "length": length}
    old = json.loads((ROOT / "mse_strap_check/layout_snapshot.json").read_text())
    assert abs(old["frame_angle_deg"] - result["frame_angle_deg"]) < 1e-12 and all(abs(x - y) < 1e-12 for x, y in zip(old["frame_origin_ft"], origin)), \
        "model frame changed: bent centres must be re-derived"
    result["bents"] = [{"id": b["id"], "station": b["station"], "center": b["center"]} for b in old["bents"]]
    result["bent_centre_source"] = "mse_strap_check/layout_snapshot.json (13 October 2026); frame and support stations unchanged"
    return result


if __name__ == "__main__":
    result = extract()
    text = json.dumps(result, indent=1) + "\n"
    if "--check" in sys.argv:
        assert OUT.read_text(encoding="utf-8") == text, "mse_layout_20261019.json differs from a fresh extraction"
        print("mse_layout_20261019.json is current")
    else:
        OUT.write_text(text, encoding="utf-8")
        print(json.dumps({"model_sha256": result["model_sha256"], "walls": len(result["walls"])}))
