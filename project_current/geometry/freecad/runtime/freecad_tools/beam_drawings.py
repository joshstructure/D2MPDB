"""Native beam sheets and a live schedule; adapted from the supplied macro APIs.

The reference macros are never executed. Physical model objects are not edited.
"""
import json
import hashlib
import math
import re
import time
import traceback
import uuid
from datetime import datetime, timezone
from html import escape

import FreeCAD as App
import FreeCADGui as Gui
import Part

from . import beam, beam_hooks
from .geometry import bounds, length, result

PAGE_W, PAGE_H = 431.8, 279.4
PAGES = ('BeamAssemblySheet','BeamDetailSheet')
VIEWS = {
    'BeamElevation':(0,(18,59,282,151),1/12),
    'BeamPlan':(0,(18,180,282,242),1/12),
    'BeamSection':(0,(311,65,404,176),1/12),
    'BottomBarDetail':(1,(28,58,199,108),1/16),
    'TopBarDetail':(1,(28,139,199,179),1/16),
    'SideBarDetail':(1,(28,218,199,232),1/16),
    'StirrupDetail':(1,(239,187,318,240),1/16),
}
ROWS = [('B1','BottomBars','Bottom'),('T1','TopBars','Top'),
        ('W1','SideBarsLeft','Side'),('W2','SideBarsRight','Side'),('S1','Stirrups','Stirrup')]


def optional(obj,key,value):
    if key in obj.PropertiesList:
        setattr(obj,key,value)


def model_state(doc):
    s=beam_hooks.state(doc)
    s.pop('document_objects')
    return s


def style(view,scale):
    view.ScaleType='Custom'
    view.Scale=scale
    view.Perspective=False
    view.CoarseView=False
    view.HardHidden=True
    view.SmoothHidden=True
    view.SmoothVisible=True
    view.SeamHidden=False
    view.SeamVisible=False
    optional(view,'IsoVisible',False)
    optional(view,'IsoHidden',False)
    for key,val in [('LineWidth',0.22),('HiddenWidth',0.10),('KeepLabel',False),
                    ('ArcCenterMarks',False),('FaceTransparency',100)]:
        optional(view.ViewObject,key,val)


def projection_box(view):
    edges=list(view.getVisibleEdges(False))+list(view.getHiddenEdges(False))
    if not edges:
        raise ValueError('No projected edges in '+view.Name)
    bs=[bounds(e) for e in edges]
    return (min(b.XMin for b in bs),min(b.YMin for b in bs),max(b.XMax for b in bs),max(b.YMax for b in bs))


def wait_projection(doc,view):
    from PySide import QtCore, QtWidgets
    doc.recompute()
    deadline=time.monotonic()+25
    previous=None
    stable=0
    last_error=None
    while time.monotonic()<deadline:
        # HLR completion is queued to the GUI event loop. updateGui alone only
        # repaints and leaves that result pending while this MCP call runs.
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents,100)
        Gui.updateGui()
        try:
            now=tuple(round(v,6) for v in projection_box(view))+(len(view.getVisibleEdges(False)),)
            stable=stable+1 if now==previous else 0
            previous=now
            if stable>=3:
                return
        except Exception as exc:
            last_error=str(exc)
            stable=0
        time.sleep(.1)
    raise RuntimeError('Native projection not ready: '+view.Name+'; '+str(last_error))


def fit(view,frame):
    b=projection_box(view)
    if b[2]-b[0]>frame[2]-frame[0] or b[3]-b[1]>frame[3]-frame[1]:
        raise ValueError('Native view exceeds reserved sheet frame: '+view.Name)
    view.X=(frame[0]+frame[2]-b[0]-b[2])/2
    view.Y=PAGE_H-(frame[1]+frame[3]-b[1]-b[3])/2


def template(kind):
    title='R-01 | ASSEMBLY / PLAN / TRUE SECTION' if kind==0 else 'R-02 | BAR DETAILS / LIVE QUANTITIES'
    out=['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" xmlns:freecad="http://www.freecadweb.org/wiki/index.php?title=Svg_Namespace" width="431.8mm" height="279.4mm" viewBox="0 0 431.8 279.4">',
         '<rect x="12.7" y="12.7" width="406.4" height="254" fill="white" stroke="#223344" stroke-width="0.35"/>',
         '<path d="M12.7 33 H419.1 M12.7 248 H419.1" stroke="#223344" stroke-width="0.25"/>',
         '<g font-family="Arial, sans-serif" fill="#172b3a">']
    def text(x,y,s,size=2.8,bold=False,center=False):
        out.append('<text x="{}" y="{}" font-size="{}"{}{}>{}</text>'.format(x,y,size,
                   ' font-weight="bold"' if bold else '', ' text-anchor="middle"' if center else '',escape(s)))
    text(18,22,'REINFORCED CONCRETE BEAM',4.5,True)
    text(18,29,title+'  |  17 x 11 in  |  DEMONSTRATION',2.7)
    if kind==0:
        for x,y,s in [(150,43,'ELEVATION - LOOKING +Y'),(150,168,'PLAN'),(358,43,'SECTION A-A')]:
            text(x,y,s,3.1,True,True)
            text(x,y+6,'Scale 1:12',2.6,False,True)
        text(358,55,'Mid-length; looking +X',2.6,False,True)
        notes=['Repeated bars overlap in projection.',
               'Use section and schedule for counts.',
               'Concrete edges define beam dimensions.',
               'Section cuts original, unfused solids.',
               'Nominal bar envelopes; ribs omitted.']
        for n,s in enumerate(notes): text(294,195+n*7,s,2.6)
    else:
        for x,y,s in [(111,43,'B1 - BOTTOM BAR CENTERLINE'),(111,124,'T1 - TOP BAR CENTERLINE'),
                      (111,199,'W1 / W2 - SIDE BAR CENTERLINE'),(278,174,'S1 - STIRRUP CENTERLINE')]:
            text(x,y,s,2.9,True,True)
            text(x,y+6,'Scale 1:16',2.5,False,True)
        text(317,43,'LIVE REINFORCEMENT SCHEDULE',3.1,True,True)
        notes=['CL = centerline.', 'Dimensions are model-linked.', 'Lengths include modeled bends.',
               'Not fabrication cut lengths.', 'Hook development not designed.', 'Quantities update on recompute.']
        for n,s in enumerate(notes): text(326,186+n*8,s,2.4)
    text(18,255,'NOT FOR CONSTRUCTION - Illustrative reinforcement; no structural or anchorage-development approval.',2.6,True)
    text(18,262,'Native source-linked views and quantities. Dimensions retain full model precision; table display rounds to 0.001.',2.5)
    out.append('</g></svg>')
    return '\n'.join(out)


def make_schedule(doc):
    sheet=doc.addObject('Spreadsheet::Sheet','BeamSchedule')
    sheet.Label='LIVE beam reinforcement and concrete quantities'
    headers=['Mark','US #','Qty','Dia (in)','Each CL (in)','Total CL (ft)','c/c (in)']
    for col,title in zip('ABCDEFG',headers): sheet.set(col+'1',title)
    for row,(mark,name,prefix) in enumerate(ROWS,2):
        sheet.set('A'+str(row),mark)
        sheet.set('B'+str(row),'=BeamInputs.'+prefix+'BarNumber')
        sheet.set('C'+str(row),'='+name+'.Amount')
        raw={'J':name+'.Diameter / (1 in)', 'K':name+'.Length / (1 in)',
             'L':name+'.TotalLength / (1 ft)', 'M':name+'.Spacing / (1 in)'}
        for col,expr in raw.items(): sheet.set(col+str(row),'='+expr)
        for col,rawcol in zip('DEFG','JKLM'):
            sheet.set(col+str(row),'=round('+rawcol+str(row)+' * 1000) / 1000')
    sheet.set('A7','TOTAL')
    sheet.set('C7','='+' + '.join(n+'.Amount' for n in beam.SETS))
    sheet.set('L7','='+' + '.join(n+'.TotalLength / (1 ft)' for n in beam.SETS))
    sheet.set('F7','=round(L7 * 1000) / 1000')
    summary=[('OVERALL / CONCRETE / HOOKS','VALUE'),
             ('Overall concrete length (ft)','=BeamInputs.Length / (1 ft)'),
             ('Concrete width / height (in)','=BeamInputs.Width / (1 in)'),
             ('Concrete height (in)','=BeamInputs.Height / (1 in)'),
             ('Gross concrete volume (ft^3)','=ConcreteBeam.Length * ConcreteBeam.Width * ConcreteBeam.Height / (1 ft^3)'),
             ('Gross concrete volume (yd^3)','=round(ConcreteBeam.Length * ConcreteBeam.Width * ConcreteBeam.Height / (1 yd^3) * 1000) / 1000'),
             ('Specified minimum cover (in)','=BeamInputs.Cover / (1 in)'),
             ('B1 inside bend / tail (in)','=BeamInputs.BottomHookInsideDiameter / (1 in)'),
             ('T1 inside bend / tail (in)','=BeamInputs.TopHookInsideDiameter / (1 in)')]
    for row,(label,value) in enumerate(summary,9):
        sheet.mergeCells('A'+str(row)+':D'+str(row))
        sheet.mergeCells('E'+str(row)+':G'+str(row))
        sheet.set('A'+str(row),label)
        sheet.set('E'+str(row),value)
    # Separate hook tails keep cells numeric and independently linked.
    sheet.set('A16','B1 inside bend diameter (in)')
    sheet.set('A17','T1 inside bend diameter (in)')
    for row,prefix in ((18,'Bottom'),(19,'Top')):
        sheet.mergeCells('A'+str(row)+':D'+str(row))
        sheet.mergeCells('E'+str(row)+':G'+str(row))
        sheet.set('A'+str(row),('B1' if prefix=='Bottom' else 'T1')+' hook straight tail (in)')
        sheet.set('E'+str(row),'=BeamInputs.'+prefix+'HookTail / (1 in)')
    sheet.set('A11','Concrete width (in)')
    for col,width in zip('ABCDEFG',(73,57,46,91,131,112,100)):
        sheet.setColumnWidth(col,width)
    for row in range(1,20): sheet.setRowHeight(str(row),20)
    sheet.setRowHeight('8',8)
    for region in ('A1:G1','A7:G7','A9:G9'):
        sheet.setStyle(region,'bold','add')
        sheet.setBackground(region,(0.88,0.92,0.95))
    sheet.setAlignment('B1:G7','center','keep')
    beam.prop(doc.BeamQuantities,'App::PropertyLink','Schedule',sheet,'Presentation')
    doc.recompute()
    return sheet


def make_page(doc,index,folder):
    name=PAGES[index]
    path=folder/(name+'-template.svg')
    path.write_text(template(index),encoding='utf-8')
    page=doc.addObject('TechDraw::DrawPage',name)
    page.Label='R-01 - Assembly, plan and section' if index==0 else 'R-02 - Bar details and LIVE quantities'
    svg=doc.addObject('TechDraw::DrawSVGTemplate',name+'Template')
    svg.Template=str(path)
    page.Template=svg
    page.Scale=1/12 if index==0 else 1/16
    optional(page,'KeepUpdated',True)
    optional(page.ViewObject,'ShowFrames',False)
    # This installed GUI lazily creates projection infrastructure when the
    # page is shown. Hidden, never-opened pages otherwise retain empty HLR.
    page.ViewObject.show()
    from PySide import QtWidgets
    QtWidgets.QApplication.processEvents()
    return page


def part_view(doc,page,name,sources,direction,xdir=(1,0,0)):
    view=doc.addObject('TechDraw::DrawViewPart',name)
    page.addView(view)
    view.Source=sources
    view.Direction=App.Vector(*direction)
    view.XDirection=App.Vector(*xdir)
    style(view,VIEWS[name][2])
    wait_projection(doc,view)
    fit(view,VIEWS[name][1])
    return view


def dim_style(dim):
    dim.Arbitrary=False
    dim.ShowUnits=True
    dim.FormatSpec='%.3w'
    for key,val in [('Font','Arial'),('Fontsize',2.7),('Arrowsize',1.6),('LineWidth',.16)]:
        optional(dim.ViewObject,key,val)


def extent_dimension(doc,page,name,view,host,orientation,key,x,y):
    dim=doc.addObject('TechDraw::DrawViewDimExtent',name)
    dim.Type='DistanceX' if orientation==0 else 'DistanceY'
    dim.DirExtent=orientation
    refs=[(host,tuple('Edge'+str(n) for n in range(1,len(host.Shape.Edges)+1)))]
    dim.Source=[(view,('',))]
    dim.Source3d=refs
    dim.References2D=[(view,('',))]
    dim.References3D=refs
    dim.MeasureType='Projected'
    page.addView(dim)
    dim_style(dim)
    beam.prop(dim,'App::PropertyString','ExpectedProperty',key,'Validation')
    dim.X=x
    dim.Y=y
    return dim


def detail_dimensions(doc,page,view,prefix):
    lines=[]
    arcs=[]
    for idx,edge in enumerate(view.getVisibleEdges()):
        if isinstance(edge.Curve,Part.Circle): arcs.append((idx,edge))
        elif len(edge.Vertexes)==2 and abs(edge.Vertexes[0].Point.x-edge.Vertexes[1].Point.x)<1e-6:
            lines.append((idx,edge))
    if len(lines)!=2 or len(arcs)!=2 or view.getHiddenEdges():
        raise ValueError('Hook detail must expose exactly two tails and two arcs')
    lines.sort(key=lambda p:p[1].CenterOfMass.x)
    arcs.sort(key=lambda p:p[1].Curve.Center.x)
    dims=[]
    for kind,idx,edge,key in [('Distance',lines[0][0],lines[0][1],prefix+'HookTail'),
                              ('Radius',arcs[1][0],arcs[1][1],prefix+'HookRadius')]:
        dim=doc.addObject('TechDraw::DrawViewDimension',prefix+kind+'Dimension')
        dim.Type=kind
        dim.References2D=[(view,'Edge'+str(idx))]
        page.addView(dim)
        dim_style(dim)
        beam.prop(dim,'App::PropertyString','ExpectedProperty',key,'Validation')
        p=edge.CenterOfMass
        dim.X=p.x-10 if kind=='Distance' else p.x+12
        dim.Y=-p.y
        if kind=='Radius':
            dim.FormatSpec='R %.3w (CL)'
            optional(dim.ViewObject,'StandardAndStyle','ASME Referencing')
        dims.append(dim)
    return dims


def build(doc,folder):
    controls=doc.addObject('App::FeaturePython','BeamDrawingControls')
    controls.Label='Drawing controls - source-linked'
    beam.prop(controls,'App::PropertyLength','SectionX',group='Section',expression='BeamInputs.Length / 2')
    sheet=make_schedule(doc)
    pages=[make_page(doc,n,folder) for n in (0,1)]
    a,d=pages
    sources=[doc.ConcreteBeam]+[doc.getObject(n) for n in beam.SETS]
    front=part_view(doc,a,'BeamElevation',sources,(0,-1,0))
    plan=part_view(doc,a,'BeamPlan',sources,(0,0,1))
    sec=doc.addObject('TechDraw::DrawViewSection','BeamSection')
    a.addView(sec)
    sec.Source=sources
    sec.BaseView=front
    sec.SectionSymbol='A'
    sec.SectionDirection='Right'
    sec.SectionNormal=App.Vector(1,0,0)
    sec.Direction=App.Vector(1,0,0)
    sec.XDirection=App.Vector(0,1,0)
    sec.SectionOrigin=App.Vector(controls.SectionX.Value,0,0)
    sec.setExpression('SectionOrigin.x','BeamDrawingControls.SectionX / (1 mm)')
    sec.FuseBeforeCut=False
    sec.CutSurfaceDisplay='Hide'
    optional(sec,'UsePreviousCut',False)
    style(sec,VIEWS['BeamSection'][2])
    optional(front.ViewObject,'ShowSectionLine',True)
    wait_projection(doc,sec)
    fit(sec,VIEWS['BeamSection'][1])
    bottom=part_view(doc,d,'BottomBarDetail',[doc.BottomBars.Base],(0,-1,0))
    top=part_view(doc,d,'TopBarDetail',[doc.TopBars.Base],(0,-1,0))
    part_view(doc,d,'SideBarDetail',[doc.SideBarsLeft.Base],(0,0,1))
    part_view(doc,d,'StirrupDetail',[doc.Stirrups.Base],(1,0,0),(0,1,0))
    dims=[]
    f=projection_box(front)
    dims.append(extent_dimension(doc,a,'BeamLengthDimension',front,doc.ConcreteBeam,0,'Length',0,-f[1]+9))
    dims.append(extent_dimension(doc,a,'BeamHeightDimension',front,doc.ConcreteBeam,1,'Height',f[0]-12,0))
    p=projection_box(plan)
    dims.append(extent_dimension(doc,a,'BeamWidthDimension',plan,doc.ConcreteBeam,1,'Width',p[0]-12,0))
    dims.extend(detail_dimensions(doc,d,bottom,'Bottom'))
    dims.extend(detail_dimensions(doc,d,top,'Top'))
    table=doc.addObject('TechDraw::DrawViewSpreadsheet','BeamScheduleView')
    d.addView(table)
    table.Source=sheet
    table.CellStart='A1'
    table.CellEnd='G19'
    table.Font='Arial'
    table.TextSize=10
    table.LineWidth=.35
    table.ScaleType='Custom'
    table.Scale=1
    optional(table.ViewObject,'LegacyScaling',True)
    optional(table.ViewObject,'KeepLabel',False)
    table.X=316
    table.Y=PAGE_H-104
    for page in pages:
        beam.prop(page,'App::PropertyLinkList','CheckedDimensions',[o for o in dims if o in page.Views],'Validation')
    beam.prop(d,'App::PropertyLink','ScheduleView',table,'Sources')
    presentation_adjustments(doc)
    doc.recompute()
    for name in VIEWS: wait_projection(doc,doc.getObject(name))
    return pages


def presentation_adjustments(doc):
    # Move the length text along its native dimension line clear of the
    # centered section marker; its measured endpoints remain source-linked.
    doc.BeamLengthDimension.X=-40
    sec=doc.BeamSection
    # A point at the beam center defines the same infinite X-normal plane,
    # and centers the native section marker on its parent elevation.
    sec.setExpression('SectionOrigin.y','BeamInputs.Width / (2 mm)')
    sec.setExpression('SectionOrigin.z','BeamInputs.Height / (2 mm)')
    sec.HardHidden=False
    sec.SmoothHidden=False
    doc.BeamSchedule.set('E13','=ConcreteBeam.Length * ConcreteBeam.Width * ConcreteBeam.Height / (1 ft^3)')
    doc.BeamSchedule.set('E14','=round(ConcreteBeam.Length * ConcreteBeam.Width * ConcreteBeam.Height / (1 yd^3) * 1000) / 1000')
    for prefix,name in [('Bottom','BottomBarDetail'),('Top','TopBarDetail')]:
        view=doc.getObject(name)
        arcs=[e for e in view.getVisibleEdges() if isinstance(e.Curve,Part.Circle)]
        if len(arcs)!=2: raise ValueError('Expected two native hook arcs while arranging labels')
        edge=max(arcs,key=lambda e:e.Curve.Center.x)
        dim=doc.getObject(prefix+'RadiusDimension')
        p=edge.CenterOfMass
        dim.X=p.x+8
        dim.Y=-p.y+10
        optional(dim.ViewObject,'RenderingExtent','Reduced')
    if not doc.getObject('SideBarLengthDimension'):
        view=doc.SideBarDetail
        b=projection_box(view)
        dim=extent_dimension(doc,doc.BeamDetailSheet,'SideBarLengthDimension',view,
                             doc.SideBarsLeft.Base,0,'BarLength',0,-b[3]-7)
        doc.BeamDetailSheet.CheckedDimensions=list(doc.BeamDetailSheet.CheckedDimensions)+[dim]
    doc.recompute()
    wait_projection(doc,sec)
    fit(sec,VIEWS['BeamSection'][1])


def number(v):
    return float(v.Value) if hasattr(v,'Value') else float(v)


def section_plane(doc):
    plane=Part.makePlane(10000,10000,App.Vector(-5000,-5000,0))
    plane.rotate(App.Vector(),App.Vector(0,1,0),90)
    plane.translate(App.Vector(doc.BeamDrawingControls.SectionX.Value,0,0))
    return plane


def checks(doc,tol):
    checks=[]
    sheet=doc.BeamSchedule
    model_total=0
    for row,(mark,name,prefix) in enumerate(ROWS,2):
        rb=doc.getObject(name)
        physical_count=len(rb.Shape.Solids)
        diameter=rb.Diameter.Value
        physical_length=rb.Shape.Volume/(math.pi*diameter**2/4)
        model_total+=physical_count
        values={'B':getattr(doc.BeamInputs,prefix+'BarNumber'),'C':physical_count,
                'J':diameter/25.4,'K':physical_length/physical_count/25.4,
                'L':physical_length/304.8,'M':rb.Spacing.Value/25.4}
        delta={col:abs(number(sheet.get(col+str(row)))-expected) for col,expected in values.items()}
        checks.append(result(name+'.schedule_matches_physical_quantities',all(v<=1e-6 for v in delta.values()),
                             measured_count=physical_count,each_length_in=values['K'],total_length_ft=values['L'],differences=delta))
        checks.append(result(name+'.display_rounding_only',all(
            abs(number(sheet.get(col+str(row)))-round(number(sheet.get(raw+str(row))),3))<=1e-8
            for col,raw in zip('DEFG','JKLM'))))
    checks.append(result('schedule_totals',number(sheet.get('C7'))==model_total
                         and abs(number(sheet.get('L7'))-doc.BeamQuantities.TotalSteelLength.Value/304.8)<=1e-7
                         and abs(number(sheet.get('E13'))-doc.ConcreteBeam.Shape.Volume/304.8**3)<=1e-7,
                         bar_count=model_total,total_centerline_ft=number(sheet.get('L7')),
                         concrete_ft3=number(sheet.get('E13'))))
    expected_unit=App.Units.Quantity('1').Unit
    checks.append(result('concrete_quantity_display_units',all(
        not hasattr(sheet.get(cell),'Unit') or sheet.get(cell).Unit==expected_unit for cell in ('E13','E14'))))
    table=doc.BeamScheduleView
    visible_columns='ABCDEFGHIJKLMNOPQRSTUVWXYZ'[:ord(table.CellEnd[0])-ord('A')+1]
    w=sum(sheet.getColumnWidth(c) for c in visible_columns)/(96/25.4)*table.Scale
    h=sum(sheet.getRowHeight(str(r)) for r in range(1,20))/(96/25.4)*table.Scale
    tb=(number(table.X)-w/2,PAGE_H-number(table.Y)-h/2,number(table.X)+w/2,PAGE_H-number(table.Y)+h/2)
    checks.append(result('schedule_paper_fit',tb[0]>=220 and tb[1]>=52 and tb[2]<=412 and tb[3]<=164,paper_bounds_mm=tb))
    checks.append(result('live_schedule_source',doc.BeamQuantities.Schedule==sheet
                         and doc.BeamScheduleView.Source==sheet and doc.BeamScheduleView in doc.BeamDetailSheet.Views))
    for name,(page_index,frame,scale) in VIEWS.items():
        view=doc.getObject(name)
        wait_projection(doc,view)
        b=projection_box(view)
        paper=(view.X.Value+b[0],PAGE_H-view.Y.Value+b[1],view.X.Value+b[2],PAGE_H-view.Y.Value+b[3])
        checks.append(result(name+'.native_view_and_fit',view in doc.getObject(PAGES[page_index]).Views
                             and not view.Perspective and not view.CoarseView
                             and abs(view.Scale-scale)<1e-10
                             and paper[0]>=frame[0]-.01 and paper[1]>=frame[1]-.01
                             and paper[2]<=frame[2]+.01 and paper[3]<=frame[3]+.01,
                             paper_bounds_mm=paper,scale=scale))
    expected=set(['ConcreteBeam',*beam.SETS])
    for name in ('BeamElevation','BeamPlan','BeamSection'):
        checks.append(result(name+'.original_sources',set(o.Name for o in doc.getObject(name).Source)==expected))
    for name,source in [('BottomBarDetail',doc.BottomBars.Base),('TopBarDetail',doc.TopBars.Base),
                        ('SideBarDetail',doc.SideBarsLeft.Base),('StirrupDetail',doc.Stirrups.Base)]:
        checks.append(result(name+'.original_centerline',doc.getObject(name).Source==[source]))
    section=doc.BeamSection
    checks.append(result('true_unfused_midspan_section',section.TypeId=='TechDraw::DrawViewSection'
                         and section.BaseView==doc.BeamElevation and not section.FuseBeforeCut
                         and abs(section.SectionOrigin.x-doc.BeamInputs.Length.Value/2)<=tol))
    # Independently cut physical bar solids at the drawing section plane.
    plane=section_plane(doc)
    native_circles=[]
    for edge in list(section.getVisibleEdges())+list(section.getHiddenEdges()):
        if isinstance(edge.Curve,Part.Circle):
            c=edge.Curve
            if not any(abs(c.Radius-r)<=tol*section.Scale and c.Center.distanceToPoint(p)<=tol*section.Scale
                       for r,p in native_circles):
                native_circles.append((c.Radius,c.Center))
    for name in ('BottomBars','TopBars','SideBarsLeft','SideBarsRight'):
        rb=doc.getObject(name)
        count=0
        for solid in rb.Shape.Solids:
            cut=solid.section(plane)
            circles=[e for e in cut.Edges if isinstance(e.Curve,Part.Circle)
                     and abs(e.Curve.Radius-rb.Diameter.Value/2)<=tol]
            count+=len(circles)
        checks.append(result(name+'.physical_section_count',count==rb.Amount,measured=count,expected=rb.Amount))
    for diameter in sorted(set(doc.getObject(n).Diameter.Value for n in ('BottomBars','TopBars','SideBarsLeft','SideBarsRight'))):
        wanted=sum(doc.getObject(n).Amount for n in ('BottomBars','TopBars','SideBarsLeft','SideBarsRight')
                   if abs(doc.getObject(n).Diameter.Value-diameter)<1e-8)
        found=sum(abs(r-diameter/2*section.Scale)<=tol*section.Scale for r,p in native_circles)
        checks.append(result('native_section_circles_'+str(diameter/25.4)+'in',found==wanted,measured=found,expected=wanted))
    for page_name in PAGES:
        page=doc.getObject(page_name)
        checks.append(result(page_name+'.sheet_size',abs(page.Template.Width.Value-PAGE_W)<1e-7
                             and abs(page.Template.Height.Value-PAGE_H)<1e-7))
        for dim in page.CheckedDimensions:
            expected_value=getattr(doc.BeamInputs,dim.ExpectedProperty).Value
            measured=number(dim.getRawValue())
            checks.append(result(dim.Name+'.native_dimension',not dim.Arbitrary
                                 and abs(measured-expected_value)<=tol,
                                 measured_in=measured/25.4,expected_in=expected_value/25.4,
                                 text=str(dim.getText())))
    invalid=[o.Name for o in doc.Objects if any('Invalid' in str(s) or 'Error' in str(s) for s in o.State)]
    checks.append(result('drawing_dependency_state',not invalid,invalid_objects=invalid))
    return checks


def add(job):
    from .api import ROOT, document, atomic, compact, check_gui
    if set(job)-{'operation','document','targets','tolerance','request_id'}:
        raise ValueError('Unsupported drawing job fields')
    doc=document(job.get('document'))
    if job.get('targets')!=['BeamQuantities']:
        raise ValueError('Explicit BeamQuantities target required')
    tol=length(job.get('tolerance','0.001 in'),positive=True)
    req=job.get('request_id','drawings-'+uuid.uuid4().hex)
    if not isinstance(req,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',req):
        raise ValueError('Invalid request_id')
    path=ROOT/'reports/transactions'/(req+'.json')
    if path.exists():
        prior=json.loads(path.read_text(encoding='utf-8'))
        if prior['request']!=job: raise ValueError('request_id belongs to a different job')
        if prior['status'] in ('PREPARED','VALIDATED'): raise RuntimeError('Unknown outcome; inspect report and actual drawing objects')
        return compact(prior)
    check_gui(doc)
    if doc.BeamInputs.AdapterIdentifier!=beam.MARKER or 'MainEndHooks' not in doc.BeamInputs.PropertiesList:
        raise ValueError('This adapter requires the observed hooked beam')
    collisions=[n for n in (*PAGES,*VIEWS,'BeamSchedule','BeamDrawingControls','BeamScheduleView') if doc.getObject(n)]
    if collisions or 'Schedule' in doc.BeamQuantities.PropertiesList:
        raise ValueError('Drawing objects already exist; inspect instead of creating duplicates: '+str(collisions))
    before=model_state(doc)
    # Keep the original TopoShape values; .copy() deliberately allocates new
    # topology and would fail isEqual even before any drawing change.
    shapes={n:doc.getObject(n).Shape for n in ('ConcreteBeam',*beam.SETS)}
    # TechDraw populates display tessellation caches on source shapes. Compare
    # exact analytic BRep serialization without those nonphysical mesh caches.
    # cleaned() operates on a returned copy, never on the model shape.
    shape_hashes={n:hashlib.sha256(s.cleaned().exportBrepToString().encode()).hexdigest() for n,s in shapes.items()}
    existing_names=set(o.Name for o in doc.Objects)
    folder=ROOT/'reports/drawings'/doc.Name
    folder.mkdir(parents=True,exist_ok=True)
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'operation':'add_beam_drawings',
            'document':doc.Name,'targets':['BeamQuantities'],'transaction_id':req,'request':job,
            'status':'PREPARED','checks':[],'errors':[],'recompute':'NOT RUN','rollback':'NOT NEEDED',
            'warnings':['Sheets and quantities describe the demonstration model; not fabrication or structural approval.'],
            'saved':False,'report_path':str(path),'changes':{'sheets':{'old':0,'new':2},'visible_live_schedule':{'old':False,'new':True}}}
    atomic(path,record)
    old_undo=doc.UndoMode
    opened=False
    try:
        if not old_undo: doc.UndoMode=1
        doc.openTransaction('CAD_AI '+req)
        opened=True
        build(doc,folder)
        record['recompute']='DONE'
        source_state=beam_hooks.equivalent(before,model_state(doc),tol)
        same_shapes={n:s.isEqual(doc.getObject(n).Shape) for n,s in shapes.items()}
        same_geometry={n:shape_hashes[n]==hashlib.sha256(doc.getObject(n).Shape.cleaned().exportBrepToString().encode()).hexdigest() for n in shapes}
        record['checks']=[result('physical_model_and_sources_preserved',source_state and all(same_shapes.values()) and all(same_geometry.values()),
                                 exact_same_shapes=same_shapes,identical_geometry_serialization=same_geometry)]
        record['checks'].extend(checks(doc,tol))
        record['created_objects']=sorted(set(o.Name for o in doc.Objects)-existing_names)
        if any(c['status']=='FAIL' for c in record['checks']):
            raise ValueError('Drawing or quantity validation failed; see checks')
        record['status']='VALIDATED'
        atomic(path,record)
        doc.commitTransaction()
        opened=False
        record['status']='PASS'
    except Exception as exc:
        record['status']='FAIL'
        record['errors'].append(str(exc))
        record['traceback']=traceback.format_exc()
        if opened:
            try:
                doc.abortTransaction()
                opened=False
                doc.recompute()
                okay=beam_hooks.equivalent(before,model_state(doc),tol)
                okay=okay and set(o.Name for o in doc.Objects)==existing_names
                record['rollback']='COMPLETE' if okay else 'INCOMPLETE'
            except Exception as rb_exc:
                record['rollback']='FAILED'
                record['errors'].append(str(rb_exc))
    finally:
        if not old_undo: doc.UndoMode=old_undo
    atomic(path,record)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(compact(record),allow_nan=False)+'\n')
    return compact(record)


def export_previews(doc,folder,pages=None):
    """Native SVG export and Qt rasterization for sheet-layout review only."""
    import TechDrawGui
    from PySide import QtCore, QtGui, QtSvg
    folder.mkdir(parents=True,exist_ok=True)
    outputs=[]
    for name in (PAGES if pages is None else pages):
        page=doc.getObject(name)
        page.ViewObject.ShowFrames=False
        svg=folder/(name+'.svg')
        png=folder/(name+'.png')
        TechDrawGui.exportPageAsSvg(page,str(svg))
        renderer=QtSvg.QSvgRenderer(str(svg))
        if not renderer.isValid(): raise ValueError('Invalid exported native SVG: '+name)
        image=QtGui.QImage(2040,1320,QtGui.QImage.Format_ARGB32)
        image.fill(QtGui.QColor('white'))
        painter=QtGui.QPainter(image)
        renderer.render(painter,QtCore.QRectF(0,0,2040,1320))
        painter.end()
        if not image.save(str(png)): raise ValueError('Cannot write sheet review image')
        outputs.append({'page':name,'svg':str(svg),'preview':str(png)})
    return outputs


def refresh(job):
    """Reapply tested presentation settings and validate existing native sheets."""
    from .api import ROOT, document, atomic, compact, check_gui
    doc=document(job.get('document'))
    if job.get('targets')!=list(PAGES): raise ValueError('Explicit assembly and detail sheet Names required')
    req=job.get('request_id','drawing-layout-'+uuid.uuid4().hex)
    if not isinstance(req,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',req): raise ValueError('Invalid request_id')
    tol=length(job.get('tolerance','0.001 in'),positive=True)
    path=ROOT/'reports/transactions'/(req+'.json')
    if path.exists():
        old=json.loads(path.read_text(encoding='utf-8'))
        if old['request']!=job: raise ValueError('request_id reused for another job')
        if old['status'] in ('PREPARED','VALIDATED'): raise RuntimeError('Unknown prior outcome; inspect before retry')
        return compact(old)
    check_gui(doc)
    before=model_state(doc)
    shapes={n:doc.getObject(n).Shape for n in ('ConcreteBeam',*beam.SETS)}
    hashes={n:hashlib.sha256(s.cleaned().exportBrepToString().encode()).hexdigest() for n,s in shapes.items()}
    record={'timestamp':datetime.now(timezone.utc).isoformat(),'document':doc.Name,'operation':'refresh_beam_drawings',
            'transaction_id':req,'request':job,'status':'PREPARED','checks':[],'errors':[],
            'rollback':'NOT NEEDED','saved':False,'report_path':str(path),
            'changes':{'presentation':'Centered section marker, hide geometry behind the section, readable radius leaders, side-bar length, dimensionless concrete quantity cells'}}
    atomic(path,record)
    opened=False
    try:
        doc.openTransaction('CAD_AI '+req)
        opened=True
        presentation_adjustments(doc)
        for name,(_,frame,_) in VIEWS.items():
            wait_projection(doc,doc.getObject(name))
            fit(doc.getObject(name),frame)
        doc.recompute()
        preserved=beam_hooks.equivalent(before,model_state(doc),tol)
        preserved=preserved and all(s.isEqual(doc.getObject(n).Shape) and hashes[n]==hashlib.sha256(doc.getObject(n).Shape.cleaned().exportBrepToString().encode()).hexdigest() for n,s in shapes.items())
        record['checks']=[result('physical_model_preserved',preserved)]+checks(doc,tol)
        if any(c['status']=='FAIL' for c in record['checks']): raise ValueError('Drawing refresh validation failed')
        record['status']='VALIDATED'
        atomic(path,record)
        doc.commitTransaction()
        opened=False
        record['status']='PASS'
    except Exception as exc:
        record['status']='FAIL'
        record['errors'].append(str(exc))
        record['traceback']=traceback.format_exc()
        if opened:
            doc.abortTransaction()
            doc.recompute()
            record['rollback']='COMPLETE' if beam_hooks.equivalent(before,model_state(doc),tol) else 'INCOMPLETE'
    atomic(path,record)
    with (ROOT/'reports/change-journal.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(compact(record),allow_nan=False)+'\n')
    return compact(record)
