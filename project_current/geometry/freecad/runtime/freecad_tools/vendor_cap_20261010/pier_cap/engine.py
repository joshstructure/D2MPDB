"""Independent, dimension-aware evaluator for the subset used in C005.
Not the Blockpad engine. Length = inch, force = kip; angle is a separate unit.
"""
import math, re
from dataclasses import dataclass

@dataclass(frozen=True)
class Q:
    v: float
    d: tuple = (0.,0.,0.)
    def same(self,o):
        if not isinstance(o,Q):o=Q(o)
        assert all(abs(a-b)<1e-8 for a,b in zip(self.d,o.d)),(self,o)
        return o
    def __add__(self,o):o=self.same(o);return Q(self.v+o.v,self.d)
    def __sub__(self,o):o=self.same(o);return Q(self.v-o.v,self.d)
    def __neg__(self):return Q(-self.v,self.d)
    def __mul__(self,o):return Q(self.v*o.v,tuple(a+b for a,b in zip(self.d,o.d)))
    def __truediv__(self,o):return Q(self.v/o.v,tuple(a-b for a,b in zip(self.d,o.d)))
    def __pow__(self,o):
        assert o.d==(0.,0.,0.),o
        return Q(self.v**o.v,tuple(a*o.v for a in self.d))
    def cmp(self,o,op):
        o=self.same(o)
        return {'<':self.v<o.v,'>':self.v>o.v,'<=':self.v<=o.v,'>=':self.v>=o.v,'==':abs(self.v-o.v)<1e-10,'!=':abs(self.v-o.v)>=1e-10}[op]

UNITS={'in':Q(1,(1,0,0)),'ft':Q(12,(1,0,0)),'kip':Q(1,(0,1,0)),
       'ksi':Q(1,(-2,1,0)),'psi':Q(.001,(-2,1,0)),'deg':Q(math.pi/180,(0,0,1))}
TOKEN=re.compile(r'\s*("(?:[^"\\]|\\.)*"|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_\u0370-\u03ff][A-Za-z_0-9.\u0370-\u03ff]*|<=|>=|==|!=|[()+\-*/^,<>])')

def parse(s):
    s=s.strip()
    ts=[];pos=0
    while pos<len(s):
        m=TOKEN.match(s,pos)
        if not m:raise ValueError(('TOKEN',s[pos:],s))
        ts.append(m.group(1));pos=m.end()
    idx=0
    def expr(minp=0):
        nonlocal idx
        t=ts[idx];idx+=1
        if t in ['+','-']:a=('unary',t,expr(29))
        elif t=='(':
            a=expr();assert ts[idx]==')';idx+=1
        elif t.startswith('"'):a=('str',t[1:-1])
        elif re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',t):a=('num',float(t))
        elif idx<len(ts) and ts[idx]=='(':
            idx+=1;args=[]
            if ts[idx]!=')':
                while True:
                    args.append(expr())
                    if ts[idx]!=',':break
                    idx+=1
            assert ts[idx]==')';idx+=1;a=('call',t,args)
        else:a=('name',t)
        while idx<len(ts):
            op=ts[idx]
            implicit=op in UNITS
            if implicit:op='*'
            p={'==':5,'!=':5,'<':5,'>':5,'<=':5,'>=':5,'+':10,'-':10,'*':20,'/':20,'^':30}.get(op,-1)
            if p<minp:break
            if not implicit:idx+=1
            b=expr(p if op=='^' else p+1)
            a=('bin',op,a,b)
        return a
    result=expr();assert idx==len(ts),(s,ts[idx:]);return result

class Engine:
    def __init__(self,definitions,externals=None,overrides=None):
        self.defs={};self.functions={};self.cache=dict(externals or {});self.overrides=overrides or {};self.stack=[]
        for item in definitions:
            f=item['formula']; lhs,rhs=f.split(' = ',1)
            rhs=re.sub(r'\s+to\s+[A-Za-z0-9^*/ ]+$','',rhs)
            if '(' in lhs:
                name,args=lhs.split('(',1);self.functions[name]=([a.strip() for a in args[:-1].split(',')],parse(rhs))
            else:
                assert lhs not in self.defs,('DUPLICATE',lhs)
                self.defs[lhs]=parse(rhs)
    def fork(self,overrides=None):
        other=object.__new__(type(self))
        other.defs=self.defs;other.functions=self.functions
        other.cache={};other.overrides=overrides or {};other.stack=[]
        return other
    def get(self,name):
        if name in self.overrides:return self.overrides[name]
        if name in self.cache:return self.cache[name]
        if name in UNITS:return UNITS[name]
        if name in ['true','false']:return name=='true'
        assert name not in self.stack,('CYCLE',name,self.stack)
        self.stack.append(name)
        try:v=self.eval(self.defs[name],{})
        except Exception as e:raise ValueError((name,str(e))) from e
        finally:self.stack.pop()
        self.cache[name]=v;return v
    def eval(self,a,scope):
        k=a[0]
        if k=='num':return Q(a[1])
        if k=='str':return a[1]
        if k=='name':return scope[a[1]] if a[1] in scope else self.get(a[1])
        if k=='unary':
            v=self.eval(a[2],scope);return -v if a[1]=='-' else v
        if k=='bin':
            x=self.eval(a[2],scope);y=self.eval(a[3],scope);op=a[1]
            if op=='+':return x+y
            if op=='-':return x-y
            if op=='*':return x*y
            if op=='/':return x/y
            if op=='^':return x**y
            if isinstance(x,Q):return x.cmp(y,op)
            return x==y if op=='==' else x!=y
        name,args=a[1:]
        if name=='If':return self.eval(args[1] if self.eval(args[0],scope) else args[2],scope)
        v=[self.eval(x,scope) for x in args]
        if name in self.functions:
            params,body=self.functions[name];assert len(params)==len(v)
            return self.eval(body,dict(zip(params,v)))
        if name in ['Min','Max']:
            for x in v:v[0].same(x)
            return (min if name=='Min' else max)(v,key=lambda x:x.v)
        if name=='Sqrt':return v[0]**Q(.5)
        if name=='Abs':return Q(abs(v[0].v),v[0].d)
        if name=='Round':return Q(round(v[0].v,int(v[1].v)),v[0].d)
        if name=='Floor':
            if v[1].d != (0,0,0):raise ValueError('Floor multiplier must be unitless')
            return Q(math.floor(v[0].v/v[1].v)*v[1].v,v[0].d)
        if name=='And':return all(v)
        if name=='Or':return any(v)
        if name=='Not':return not v[0]
        if name in ['Tan','Sin','Cos']:
            assert v[0].d==(0,0,1)
            return Q(getattr(math,name.lower())(v[0].v))
        raise ValueError(('FUNCTION',name))
    def all(self):
        for n in self.defs:self.get(n)
        return self.cache
    def text(self,v,unit=None,places=3):
        if isinstance(v,bool):return str(v).lower()
        if not isinstance(v,Q):return v
        if unit:
            u=self.eval(parse('1 '+unit),{});v.same(u);number=v.v/u.v
            return f'{number:.{places}f} {unit}'
        assert v.d==(0,0,0),(v,unit)
        return f'{v.v:.{places}f}'

class ScalarEngine(Engine):
    """Fast search evaluator, same parsed formulas in fixed inch/kip/radian units.

    Unit-aware Engine rechecks every displayed finalist; scalar results are tested
    against it. Case imports never supply executable formulas.
    """
    def get(self,name):
        if name in UNITS:return UNITS[name].v
        return super().get(name)

    def eval(self,a,scope):
        k=a[0]
        if k in ('num','str'):return a[1]
        if k=='name':return scope[a[1]] if a[1] in scope else self.get(a[1])
        if k=='unary':
            v=self.eval(a[2],scope);return -v if a[1]=='-' else v
        if k=='bin':
            x=self.eval(a[2],scope);y=self.eval(a[3],scope);op=a[1]
            if op=='+':return x+y
            if op=='-':return x-y
            if op=='*':return x*y
            if op=='/':return x/y
            if op=='^':return x**y
            if op=='<':return x<y
            if op=='>':return x>y
            if op=='<=':return x<=y
            if op=='>=':return x>=y
            if op=='==':return abs(x-y)<1e-10 if isinstance(x,(int,float)) else x==y
            if op=='!=':return abs(x-y)>=1e-10 if isinstance(x,(int,float)) else x!=y
        name,args=a[1:]
        if name=='If':return self.eval(args[1] if self.eval(args[0],scope) else args[2],scope)
        v=[self.eval(x,scope) for x in args]
        if name in self.functions:
            params,body=self.functions[name]
            return self.eval(body,dict(zip(params,v)))
        if name=='Min':return min(v)
        if name=='Max':return max(v)
        if name=='Sqrt':return math.sqrt(v[0])
        if name=='Abs':return abs(v[0])
        if name=='Round':return round(v[0],int(v[1]))
        if name=='Floor':return math.floor(v[0]/v[1])*v[1]
        if name=='And':return all(v)
        if name=='Or':return any(v)
        if name=='Not':return not v[0]
        if name in ('Tan','Sin','Cos'):return getattr(math,name.lower())(v[0])
        raise ValueError(('FUNCTION',name))
