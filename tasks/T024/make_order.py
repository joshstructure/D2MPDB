"""T024: write component_order.json, the registered component order passed to `prepare --order` (modules permuted among the
module slots; everything else in place). Not order.json, which is the workflow's task contract.

Basis modules first, then the calculations C001 to C016 in numerical order (each code-reference packet right after its
calculation), then quantities, decision log, notes, the general reference index and the archives."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools.bpad_workflow import Journal, MODULE_TAGS  # noqa: E402

MODULES = [
    'report:PedBridge', 'report:ProjectInfo', 'report:Materials', 'report:BridgeGeometry_2Beam', 'report:AccessGeometry',
    'report:PileProperties', 'spreadsheet:PedBridgeWeights_2Beams', 'report:GeneralLoads', 'report:PedBridgeWind',
    'report:LoadCombinations', 'report:FBMPPier', 'report:FBMPEndBent', 'report:FoundationModeling',
    'report:C001WindLoadOnPedBridgeSuperstructure', 'report:CodeReferencesC001',
    'report:FenceWind', 'report:CodeReferencesC002',
    'report:BridgeMovement', 'report:CodeReferencesC003',
    'report:SuperstructureUplift', 'report:CodeReferencesC004',
    'report:PierWallFins',
    'report:CapDesignBasis', 'report:CapDesignEndBentOne', 'report:CapDesignEndBentTwo', 'report:CapDesignPier',
    'report:PileDesignEndBentOne', 'report:PileDesignEndBentTwo', 'report:PileDesignPier',
    'report:EndBentBackwallDesign', 'report:MSEWallExclusion', 'report:BearingDesign',
    'spreadsheet:QauntitiesBridge', 'spreadsheet:QuantitiesMSEWall', 'report:DecisionLog', 'report:Notes',
    'report:CodeReferencesGeneral', 'report:BridgeGeometry_3Beam', 'spreadsheet:PedBridgeWeights_3Beams', 'report:VoidPedBridge',
]
journal = Journal.load(ROOT / 'journal' / 'D2_I95_Project_Journal.bpad')
current_modules = [k for k in journal.order if k.split(':', 1)[0] in MODULE_TAGS]
assert sorted(current_modules) == sorted(MODULES), (set(current_modules) ^ set(MODULES))
modules = iter(MODULES)
order = [next(modules) if k.split(':', 1)[0] in MODULE_TAGS else k for k in journal.order]
journal.reorder(order)                                  # validates
(TASK / 'component_order.json').write_text(json.dumps(order, indent=1) + '\n', encoding='utf-8')
print(json.dumps({'base_sha256': journal.sha256, 'modules': len(MODULES), 'first_module_slot': order.index(MODULES[0])}))
