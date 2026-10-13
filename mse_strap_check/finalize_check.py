"""Cache independently checked results and render source-linked plan previews.

Neither this script nor its PNGs are a native Blockpad rendering.
"""
from pathlib import Path
import json, re, math, hashlib
from lxml import etree as E
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Polygon
from verify_check import engine,parse,Q,definitions

HERE=Path(__file__).resolve().parent
path=HERE/'MSE Strap Clearance - Both End Bents.bpad'
tree=E.parse(str(path))
def qualify(r,text):
    names={f['formula'].split(' = ')[0].split('(')[0].split('.',1)[1] for f in definitions if f['formula'].startswith(r+'.')}
    return re.sub(r'(?<![\w.])([A-Za-z][A-Za-z0-9]*)(?![\w.])',lambda m:r+'.'+m[1] if m[1] in names else m[1],text)
def evaluate(r,formula):
    f=re.sub(r'\s+to\s+[A-Za-z0-9^*/ ]+$','',formula)
    return engine.eval(parse(qualify(r,f)),{})
def printable(v,formula):
    if isinstance(v,bool):return str(v).lower()
    if not isinstance(v,Q):return v
    unit=None
    if v.d==(1,0,0):
        unit='in' if re.search(r'(?:to|=)\s*[^=]*\bin$',formula) or any(k in formula for k in ['Width','width','extra','Gap','gap','Tolerance','Clear']) else 'ft'
        if formula.endswith('to ft'):unit='ft'
    elif v.d==(0,0,1):unit='deg'
    return engine.text(v,unit,3)
count=0
for report in tree.findall('report'):
    rid=report.get('name')
    for el in report.xpath('.//dynexp | .//c[@formula]'):
        f=el.get('formula');lhs=f.split(' = ')[0]
        if ' = ' in f:
            if '(' in lhs:continue
            value=engine.get(rid+'.'+lhs)
        else:value=evaluate(rid,f)
        for c in list(el):
            if c.tag in ['expresult','num','bool','textvalue']:el.remove(c)
        text=printable(value,f)
        if el.tag=='dynexp':E.SubElement(el,'expresult').text=(' = ' if ' = ' in f else '')+text
        else:
            tag='bool' if isinstance(value,bool) else 'num' if isinstance(value,Q) else 'textvalue'
            E.SubElement(el,tag).text=text
        count+=1
tree.write(str(path),encoding='utf-8',xml_declaration=True,pretty_print=True)

def value(key):return engine.get(key).v/12
def num(key):return engine.get(key).v
def get(r,s):return value(r+'.'+s)
fig,axs=plt.subplots(2,2,figsize=(14,12.5),gridspec_kw={'height_ratios':[1.25,.7]},layout='constrained')
fig.get_layout_engine().set(rect=(0,.045,1,.955))
fig.patch.set_facecolor('#F5F8FA')
fig.suptitle('MSE STRAP CLEARANCE | BOTH END BENTS\n2 in trial strap - 15 degree skew - nominal pile positions',fontsize=18,fontweight='bold',color='#163947')
for col,r in enumerate(['EB1','EB2']):
    ax=axs[0,col];ax.set_facecolor('white')
    for k in range(1,6):
        xa,xb,ya,yb=[get(r,f'W{k}'+t) for t in ['xmin','xmax','ymin','ymax']]
        ax.add_patch(Rectangle((xa,ya),xb-xa,yb-ya,facecolor='#435D66',edgecolor='#213D48',lw=1,zorder=2))
    cx,cy=get(r,'CapX'),get(r,'CapY')
    ax.add_patch(Rectangle((-cx,-cy),2*cx,2*cy,facecolor='#E9EDEF',edgecolor='#758992',ls='--',lw=1.4,zorder=3))
    half=get(r,'Half')
    for j in range(1,5):
        x,y=get(r,f'P{j}x'),get(r,f'P{j}y')
        ax.add_patch(Rectangle((x-half,y-half),2*half,2*half,fc='#B9DFE7',ec='#236675',lw=1.5,zorder=5))
        ax.text(x,y,f'P{j}',ha='center',va='center',fontsize=10,zorder=8)
    ox,oy=get(r,'Ox'),get(r,'Oy');ex,ey=get(r,'Ex'),get(r,'Ey')
    vx,vy=num(r+'.Vx'),num(r+'.Vy');rad=value('Basis.Width')/2
    for s in ['Plus','Minus']:
        ax.plot([ox,get(r,'E'+s+'x')],[oy,get(r,'E'+s+'y')],color='#337DC2',lw=1.3,zorder=6,ls='--')
    corners=[(ox-vy*rad,oy+vx*rad),(ex-vy*rad,ey+vx*rad),(ex+vy*rad,ey-vx*rad),(ox+vy*rad,oy-vx*rad)]
    ax.add_patch(Polygon(corners,fc='#EAA364',ec='#BD6018',lw=1,zorder=7))
    ax.scatter([ox],[oy],s=28,c='#BD6018',zorder=9)
    ax.annotate('Anchor on P2 centerline',xy=(ox,oy),xytext=(-7.8,oy-1.55),fontsize=9,ha='left',arrowprops={'arrowstyle':'-','color':'#586E77'})
    ax.text(3.1,1.2,'CAP (above strap)',ha='center',fontsize=9,color='#586E77',zorder=9)
    ax.text(-8.05,8.8,('A6' if col==0 else 'B6')+' / left return',rotation=90,ha='center',fontsize=9,color='#263F49')
    ax.text(7.9,2.6,('A7' if col==0 else 'B7')+' / right return',rotation=90,ha='center',fontsize=9,color='#263F49')
    ax.text(5.5,oy-1.35,('A5' if col==0 else 'B1')+' / front wall',ha='center',fontsize=9,color='#263F49')
    ax.text(-7,5.8,'-15 deg',color='#337DC2',fontsize=9)
    ax.text(2.2,6.4,'+15 deg\n2 in strap',color='#BD6018',fontsize=9)
    ax.set_xlim(-11,11);ax.set_ylim(-6,16);ax.set_aspect('equal');ax.grid(alpha=.15)
    ax.set_xlabel('Across bent (ft)');ax.set_ylabel('Into approach (ft)')
    ax.set_title(f'End Bent {col+1} | front wall and return walls',loc='left',fontweight='bold',fontsize=12,color='#163947')
    detail=axs[1,col];detail.set_facecolor('white')
    x,y=get(r,'P2x'),get(r,'P2y');d=get(r,'C12d');gap=num(r+'.C12PlusPile');maxw=num(r+'.C12width')
    detail.add_patch(Rectangle((-half,-half),2*half,2*half,fc='#B9DFE7',ec='#236675',lw=1.5,zorder=4))
    dx=(d-half)*math.tan(math.pi/12)
    # Crop around the near right corner; complete strip continues from the wall.
    localcorners=[(xx-x,yy-y) for xx,yy in corners]
    detail.add_patch(Polygon(localcorners,fc='#EAA364',ec='#BD6018',lw=1.4,zorder=5,alpha=.85))
    detail.scatter([half],[-half],c='#C24035',s=45,zorder=8)
    detail.annotate(f'Edge overlap: {-gap:.3f} in',xy=(half,-half),xytext=(-1.25,-1.45),fontsize=10,color='#9F332B',arrowprops={'arrowstyle':'->','color':'#9F332B'})
    detail.text(-1.25,.7,'P2',fontsize=10,color='#236675')
    detail.set_xlim(-1.5,1.8);detail.set_ylim(-1.7,1.1);detail.set_aspect('equal');detail.grid(alpha=.15)
    detail.set_title(f'Near-corner detail | nominal max strip {maxw:.2f} in',loc='left',fontsize=11,fontweight='bold',color='#9F332B')
    detail.set_xlabel('Feet relative to P2');detail.set_ylabel('Feet relative to P2')
fig.text(.5,.012,'Illustrative width; zero added clearance/tolerance.\nEditable native formulas and route selections are in the BPAD. Preview is independently rendered, not a Blockpad screenshot.',ha='center',fontsize=8,color='#586E77')
fig.savefig(HERE/'Plan preview.png',dpi=160)
plt.close(fig)

# Render the actual live PlotLines definitions as a bounded appearance approximation.
for report in tree.findall('report'):
    canvas=report.find('.//canvas')
    if canvas is None:continue
    fig,ax=plt.subplots(figsize=(9,8.3));ax.set_aspect('equal');ax.set_xlim(0,6.5);ax.set_ylim(0,6);ax.axis('off')
    for plot in canvas.findall('plot'):
        xs,ys=plot.get('formula')[11:-2].split('],[')
        # commas inside Min/Max are not array separators
        def split(s):
            out=[];start=0;depth=0
            for i,c in enumerate(s):
                depth+=1 if c=='(' else -1 if c==')' else 0
                if c==',' and depth==0:out.append(s[start:i]);start=i+1
            return out+[s[start:]]
        def coordinate(s):
            # Null points are native plot gaps and must stay null through arithmetic.
            if 'null' in s:
                cond=s[s.index('If(')+3:s.index(',null')]
                if engine.eval(parse(cond),{}):return None
            return engine.eval(parse(s),{}).v
        xx=[coordinate(s) for s in split(xs)];yy=[coordinate(s) for s in split(ys)]
        assert all(v is None or math.isfinite(v) for v in xx+yy)
        ax.plot(xx,yy,color=plot.get('linecolor'),lw=float(plot.get('linethickness')))
    for lab in canvas.findall('planecontainer'):
        x,y,_=map(float,lab.get('origin').split(','));ax.text(x,y,lab.findtext('textvalue'),fontsize=float(lab.get('fontsize')),color=lab.get('textcolor'),va='bottom')
    fig.savefig(HERE/f'native-preview-{report.get("name")}.png',dpi=140,bbox_inches='tight');plt.close(fig)

verification=json.loads((HERE/'verification.json').read_text())
verification.update({'bpad_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'independent_display_caches':count,'native_review':{'recalculation':False,'appearance':False,'reason':'Computer Use was not approved to use Blockpad.'},'preview':'Independent plan preview and direct PlotLines geometry render; not native pagination.'})
snapshot=json.loads((HERE/'layout_snapshot.json').read_text())
for file,key in [(HERE.parent/snapshot['model_path'],'model_sha256'),(HERE.parent/'journal/D2_I95_Project_Journal.bpad','journal_sha256')]:
    assert hashlib.sha256(file.read_bytes()).hexdigest()==snapshot[key]
verification['source_model_and_journal_unchanged']=True
(HERE/'verification.json').write_text(json.dumps(verification,indent=2))
print(json.dumps({'cached_results':count,'bpad_sha256':verification['bpad_sha256'],'source_files_unchanged':True}))
