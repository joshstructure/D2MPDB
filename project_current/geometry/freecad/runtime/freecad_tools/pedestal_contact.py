"""Specified leg embedment and tangent horizontal layers, with separate design findings."""
import json,traceback,math
from pathlib import Path
from . import pedestal_ubars as p,pedestal_edges as e,bridge
from .geometry import length,result,bounds

def detail_checks(inp,embedment='12 in',layer_clearance='0 in'):
    target=length(embedment,positive=True);gap=length(layer_clearance)
    doc=inp.Document;pb=bounds(bridge.local_shape(inp.Host));bars=doc.getObject(inp.Prefix+'Quantities').Bars
    checks=[];horizontal={'X':[],'Y':[]}
    for bar in bars:
        local=bar.Shape.copy();local.Placement=inp.CageFrame.inverse().multiply(local.Placement)
        # Actual analytic vertical endpoints and solid bounds both measure cap penetration.
        ends=[];flat=[]
        for edge in bar.Base.Shape.Edges:
            if len(edge.Vertexes)!=2:continue
            a,b=[v.Point for v in edge.Vertexes]
            if abs(a.x-b.x)<1e-7 and abs(a.y-b.y)<1e-7:ends.append(min([a,b],key=lambda v:v.z))
            if abs(a.z-b.z)<1e-7:flat.append((a,b))
        actual=[pb.ZMin-v.z for v in ends]
        checks.append(result(bar.Name+'_specified_cap_embedment',len(ends)==2 and all(abs(v-target)<p.TOL for v in actual) and abs(pb.ZMin-bounds(local).ZMin-target)<p.TOL,embedments_in=[v/p.IN for v in actual]))
        if len(flat)!=1:raise ValueError('Expected one horizontal straight segment per U-bar')
        a,b=flat[0];direction='X' if abs(a.y-b.y)<1e-7 else 'Y'
        horizontal[direction].append((bar,a,b))
    contacts=0
    for xb,a,b in horizontal['X']:
        for yb,c,d in horizontal['Y']:
            if min(a.x,b.x)<=c.x<=max(a.x,b.x) and min(c.y,d.y)<=a.y<=max(c.y,d.y):
                actual_gap=a.z-c.z-(xb.Diameter.Value+yb.Diameter.Value)/2
                distance=xb.Shape.distToShape(yb.Shape)[0]
                overlap=abs(xb.Shape.common(yb.Shape).Volume)
                checks.append(result(xb.Name+'_'+yb.Name+'_layer_contact',abs(actual_gap-gap)<p.TOL and abs(distance-gap)<p.TOL and overlap==0.,clear_gap_in=actual_gap/p.IN,solid_distance_in=distance/p.IN,common_volume_mm3=overlap))
                contacts+=1
    checks.append(result(inp.Prefix+'_horizontal_crossings_present',contacts>0,crossings=contacts))
    return checks

def apply(doc,input_names,embedment,layer_clearance,request_id,report_dir):
    """Retain development failures; apply the expressly requested geometry only."""
    length(embedment,positive=True)
    if length(layer_clearance)<0:raise ValueError('Negative layer clearance')
    path=Path(report_dir)/(request_id+'.json')
    if path.exists():raise ValueError('Existing transaction; inspect before retry')
    inputs=[doc.getObject(n) for n in input_names]
    if len(inputs)!=6 or any(i is None or not getattr(i,'MaximumSpacingLayout',False) for i in inputs):raise ValueError('Six explicit edge-layout cages are required')
    protected=[o.Name for o in doc.Objects if not o.Name.startswith('PedSteel') and o.Name not in ['PedestalSteelChecks','PedestalReinforcement']]
    before=bridge.source_state(doc,protected)
    record=dict(transaction_id=request_id,status='PREPARED',input_names=input_names,embedment=embedment,layer_clearance=layer_clearance,protected=protected)
    def journal():path.write_text(json.dumps(record,indent=2)+'\n')
    journal();doc.openTransaction('Pedestal 12 inch embedment and contacting layers')
    try:
        for inp in inputs:
            inp.AutoSync=False
            e.prop(inp,'App::PropertyLength','SpecifiedEmbedment',embedment,'Specified detail')
            e.prop(inp,'App::PropertyBool','UseSpecifiedEmbedment',True,'Specified detail')
            e.prop(inp,'App::PropertyString','DevelopmentStatus','UNCHECKED','Development')
            e.prop(inp,'App::PropertyString','SpecifiedDetailBasis','2026-10-17 user direction: 12 in cap embedment; tangent horizontal layers. Calculated development remains reported independently.','Specified detail')
            inp.LayerClearance=layer_clearance;inp.AutoSync=True
            # The upper bends descend below the horizontal layer. Put the two
            # outer crossing bars at the straight-segment tangent stations, so
            # layer contact cannot clip the upper bend surfaces.
            rad=(inp.InsideBendDiameter.Value+inp.Diameter.Value)/2
            pb=bounds(bridge.local_shape(inp.Host))
            stations=[length(v) for v in inp.EdgeYStations]
            start=inp.EdgeLongitudinalStart.Value+rad
            end=pb.XLength-inp.EdgeLongitudinalEnd.Value-rad
            if inp.Host.SupportID=='Pier':
                # The pier's outer cap longitudinal bars occupy the tangent
                # station. Place the two transverse returns on their inboard
                # side, using the measured nominal solids and a 1/4 in grid.
                obstructions=[]
                for name in ['CagePierLong05','CagePierLong01']:
                    shape=doc.getObject(name).Shape.copy()
                    shape.Placement=inp.CageFrame.inverse().multiply(shape.Placement)
                    obstructions.append(bounds(shape))
                r=inp.Diameter.Value/2;increment=.25*p.IN
                start=max(start,math.ceil((obstructions[0].XMax+r-pb.XMin)/increment)*increment)
                end=min(end,math.floor((obstructions[1].XMin-r-pb.XMin)/increment)*increment)
            shifts=[max(0.,start-stations[0]),min(0.,end-stations[-1])]
            stations[0]+=shifts[0];stations[-1]+=shifts[1]
            if stations!=sorted(stations):raise ValueError('Outer transverse adjustment reverses bar order')
            inp.EdgeYStations=[format(v/p.IN,'.17g')+' in' for v in stations]
            record.setdefault('outer_transverse_adjustments_in',{})[inp.Name]=[v/p.IN for v in shifts]
            p.regenerate(inp)
            sheet=doc.getObject(inp.Prefix+'Schedule')
            p.write_schedule(inp,sheet,doc.getObject(inp.Prefix+'Quantities').Bars);doc.recompute([sheet])
        record['results']={i.Name:p.validate(i) for i in inputs}
        record['detail_checks']=[c for i in inputs for c in detail_checks(i,embedment,layer_clearance)+e.alignment_checks(i)]
        record['development_checks']=[c for r in record['results'].values() for c in r['checks'] if c.get('category')=='development']
        geometry=[c for r in record['results'].values() for c in r['checks'] if c.get('category')!='development']+record['detail_checks']
        record['geometry_failures']=[c for c in geometry if c['status']!='PASS']
        record['development_failures']=[c for c in record['development_checks'] if c['status']!='PASS']
        record['clashes']=p.clash_check(doc,inputs)
        record['protected_unchanged']=before==bridge.source_state(doc,protected)
        journal()
        if record['geometry_failures'] or record['clashes']['status']!='PASS' or not record['protected_unchanged']:raise ValueError('Physical geometry check failed; transaction aborted')
        record['geometry_status']='PASS'
        record['development_status']='FAIL' if record['development_failures'] else 'PASS'
        check=doc.getObject('PedestalSteelChecks')
        check.Status='GEOMETRY PASS; DEVELOPMENT '+record['development_status']
        check.ReportJSON=json.dumps(dict(geometry_status=record['geometry_status'],development_status=record['development_status'],development_failures=record['development_failures'],clashes=record['clashes']))
        check.Basis='Dated physical check of user-specified 12 in embedment and tangent layers. Development FAIL is retained, not waived. Rerun checks after edits.'
        doc.commitTransaction();record['status']='APPLIED_UNSAVED_WITH_DEVELOPMENT_FINDINGS' if record['development_failures'] else 'APPLIED_UNSAVED'
    except Exception:
        record.update(status='ROLLED_BACK',traceback=traceback.format_exc());doc.abortTransaction();raise
    finally:journal()
    return record
