"""Rebuild the support-section reference using FreeCAD's bundled Python.

Run with '<FreeCAD>/bin/python.exe scripts/measure_bridge_native_sections.py'.
Reads saved BReps only; never opens, recomputes or saves the source document.
Station planes use local X after removing each shape's global placement.
The fixture is tied to the exact registered source hash in project_source.json.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as App
import Part

ROOT=Path(__file__).resolve().parents[1]
FT=304.8


def main():
    receipt=json.loads((ROOT/'bridge_geometry/project_source.json').read_text())
    source=ROOT/receipt['source_file']
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=receipt['sha256']:
        raise ValueError('Registered source changed; review the source incorporation before replacing this reference.')
    archive=zipfile.ZipFile(source)
    xml=ET.fromstring(archive.read('Document.xml'))
    obj=next(o for o in xml.findall('./ObjectData/Object') if o.get('name')=='BridgePGL')
    props={p.get('name'):float(p.find('Float').get('value')) for p in obj.findall('./Properties/Property') if p.find('Float') is not None}
    start=props['StartStation']/FT
    results=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'tests') as directory:
        for sid in ('EB1','Pier','EB2'):
            shapes={}
            for name in archive.namelist():
                if not (name.endswith('.Shape.brp') and any(name.startswith(prefix+sid) for prefix in
                        ('BridgeCap','BridgePile','BridgePedestal','BridgePad'))):continue
                target=Path(directory)/name;target.write_bytes(archive.read(name))
                shape=Part.Shape();shape.read(str(target));shape.Placement=App.Placement()
                shapes[name.removesuffix('.Shape.brp')]=shape
            cap=shapes['BridgeCap'+sid].BoundBox
            center=round(start+(cap.XMin+cap.XMax)/(2*FT),8)
            width=round(cap.XLength/FT,8);underside=cap.ZMin/FT
            offsets=sorted(set([-width/2-.00001,-width/2,-1.6,-1.3,-1.29,-1.,-.876,-.875,-.82,-.78,-.6,-.5,-.46,-.45,-.125,0,
                               .125,.45,.46,.5,.6,.78,.82,.875,.876,1.,1.29,1.3,1.6,width/2,width/2+.00001]))
            for delta in offsets:
                station=center+delta;x=(station-start)*FT
                corners=[App.Vector(x,-5000,(underside-1.8)*FT),App.Vector(x,5000,(underside-1.8)*FT),
                         App.Vector(x,5000,55*FT),App.Vector(x,-5000,55*FT)]
                plane=Part.Face(Part.makePolygon(corners+[corners[0]]))
                measured=[]
                for name,shape in shapes.items():
                    cut=shape.common(plane)
                    if cut.Area/FT**2<1e-9:continue
                    box=cut.BoundBox
                    measured.append(dict(name=name,area_ft2=cut.Area/FT**2,
                        bounds_ft=[box.YMin/FT,box.YMax/FT,box.ZMin/FT,box.ZMax/FT]))
                results.append(dict(support=sid,station=station,components=measured))
    data=dict(source_sha256=digest,samples=results,
        method='Saved native BRep intersection with station plane; placements removed; pile heads cropped 1.8 ft below cap underside; no document recompute or save.')
    path=ROOT/'tests/data/bridge_native_sections.json'
    path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(f'Measured {len(results)} station cuts directly from saved native solids.')


if __name__=='__main__':main()
