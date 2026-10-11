"""FreeCAD-side no-AI launcher. Job execution shares the authoritative API."""
import json
from pathlib import Path
from .api import ROOT, run_file

def launch(path=None):
    if path is None:
        from PySide import QtWidgets
        path,_filter=QtWidgets.QFileDialog.getOpenFileName(None,'Choose CAD_AI JSON job',str(ROOT/'jobs'),'JSON jobs (*.json)')
    if not path: return None
    result=run_file(path)
    (ROOT/'reports/no-ai-latest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result
