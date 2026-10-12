"""Embed the maintained physical geometry adapter into the portable notebook."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKER='# --- Source-derived physical bridge geometry ---'


def main():
    path=ROOT/'Bridge_Geometry_2 Beam_V2.ipynb'
    nb=json.loads(path.read_text(encoding='utf-8'))
    cell=next(c for c in nb['cells'] if c.get('id')=='bridge-05')
    base=''.join(cell['source']).split(MARKER)[0].rstrip()
    adapter=(ROOT/'bridge_geometry/physical.py').read_text(encoding='utf-8')
    source=base+'\n\n'+MARKER+'\n_StationPlaneBridgeModel = BridgeModel\n\n'+adapter
    source+='\n\nclass BridgeModel(PhysicalBridgeMixin, _StationPlaneBridgeModel):\n    """Shared model with source-derived volumetric support station cuts."""\n    pass\n'
    cell['source']=source.splitlines(keepends=True)
    path.write_text(json.dumps(nb,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print('Embedded physical support geometry adapter.')


if __name__=='__main__':main()
