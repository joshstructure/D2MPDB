import math
from fractions import Fraction
import FreeCAD as App

def length(value, positive=False):
    if not isinstance(value,str) or not any(c.isalpha() or c in "'\"" for c in value):
        raise ValueError('Dimensional values require units, for example 6 in or 152.4 mm')
    q=App.Units.Quantity(value)
    if q.Unit != App.Units.Quantity('1 mm').Unit or not math.isfinite(q.Value):
        raise ValueError('Expected a finite length')
    if positive and q.Value <= 0: raise ValueError('Dimension must be positive')
    return float(q.Value)

def display(mm):
    ticks=int(math.floor(abs(mm)/25.4*16+0.5)); feet,ticks=divmod(ticks,192); inches,num=divmod(ticks,16)
    return {'mm':mm,'in':mm/25.4,'feet_inches_1_16':('-' if mm<0 else '')+str(feet)+"' "+str(inches)+((' '+str(Fraction(num,16))) if num else '')+'"'}

def bounds(shape):
    return shape.optimalBoundingBox(False,False)

def result(name,ok,**details):
    return {'name':name,'status':'PASS' if ok else 'FAIL',**details}

def solid_summary(obj):
    s=obj.Shape
    if s.isNull(): raise ValueError('Empty shape: '+obj.Name)
    b=bounds(s)
    return {'object':obj.Name,'type':obj.TypeId,'label':obj.Label,'valid':s.isValid(),'solids':len(s.Solids),'volume_in3':s.Volume/25.4**3,'bounds_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]}

def box_checks(obj,tol):
    if obj.TypeId!='Part::Box': raise ValueError('Box adapter requires native Part::Box')
    s=obj.Shape.copy(); s.Placement=obj.Placement.inverse().multiply(s.Placement)
    b=bounds(s); expected=[obj.Length.Value,obj.Width.Value,obj.Height.Value]; actual=[b.XLength,b.YLength,b.ZLength]
    volume=math.prod(expected)
    return [result('geometry',obj.Shape.isValid() and len(obj.Shape.Solids)==1),result('dimensions',max(abs(a-e) for a,e in zip(actual,expected))<=tol,measured_in=[x/25.4 for x in actual]),result('volume',abs(obj.Shape.Volume-volume)<=max(1e-7,volume*1e-8),measured_in3=obj.Shape.Volume/25.4**3,expected_in3=volume/25.4**3),result('placement',obj.Shape.CenterOfMass.distanceToPoint(obj.Placement.multVec(App.Vector(*[x/2 for x in expected])))<=tol)]

def pair(a,b,minimum,tol):
    if any(s.isNull() or not s.isValid() or not s.Solids for s in (a,b)):
        raise ValueError('Clearance requires valid nominal solids')
    distance=float(a.distToShape(b)[0]); volume=abs(float(a.common(b).Volume))
    # Positive measured common volume is overlap, independent of clearance tolerance.
    classification='OVERLAP' if volume>0 else ('CONTACT / NEAR CONTACT' if distance<=tol else 'SEPARATED')
    return result('clearance',volume==0 and distance+tol>=minimum,classification=classification,distance_in=distance/25.4,common_volume_in3=volume/25.4**3,minimum_in=minimum/25.4)

def box_cover(shape,host,minimum,tol):
    if host.TypeId!='Part::Box' or not host.Shape.isValid(): raise ValueError('Cover requires a native box host')
    local=shape.copy(); local.Placement=host.Placement.inverse().multiply(local.Placement); b=bounds(local)
    margins=[b.XMin,host.Length.Value-b.XMax,b.YMin,host.Width.Value-b.YMax,b.ZMin,host.Height.Value-b.ZMax]
    outside=abs(float(shape.cut(host.Shape).Volume))
    return result('cover',outside<=1e-7 and min(margins)+tol>=minimum,measured_minimum_in=min(margins)/25.4,faces_in=[x/25.4 for x in margins],outside_volume_mm3=outside)
