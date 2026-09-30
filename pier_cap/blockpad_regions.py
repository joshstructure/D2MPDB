"""Upgrade the existing C005 reinforcement table and native live section plots."""
import re
from lxml import etree as E
from .model import DEFINITIONS


def update_regional_views(report):
    # Preserve the journal's tables, but bind each row to its own bar size.
    for row in report.iter('row'):
        names=[e.get('formula','').split(' = ')[0] for e in row.iter('dynexp')]
        region=next((z for z in 'PB' if any(n in names for n in (f'n_{z}1',f'n_{z}2'))),None)
        if region:
            for cell in row.iter('c'):
                if 'Bar_pos' in cell.get('formula',''):
                    cell.set('formula',cell.get('formula').replace('Bar_pos','Bar_'+region))
    for text in report.iter('paragraph'):
        if text.text:
            text.text=text.text.replace('Bearing bottom row','Between-pile bottom row')
    # Formula result caches describe the source cage, not the exported inputs.
    for node in list(report.iter()):
        if node.get('formula') and node.tag!='dynexp':
            for child in list(node):
                if child.tag in ('num','textvalue','expresult'):node.remove(child)
    variables={d['name'].split('(')[0] for d in DEFINITIONS}|{'GfxRowX','GfxRowY','GfxScale'}
    def qualify(expression):
        return re.sub(r'\b[A-Za-z_]\w*\b',lambda m:'PierCapDesign.'+m[0] if m[0] in variables else m[0],expression)
    for canvas in report.iter('canvas'):
        if canvas.get('name')!='LiveReinforcementSections':continue
        for node in list(canvas):
            formula=node.get('formula','')
            if (node.tag=='plot' and 'GfxRowX' in formula and not re.search(r'\.n_[PB]U\b',formula)) or node.get('name','').startswith('NotebookPile'):
                canvas.remove(node)
            if node.tag=='planecontainer':
                text=node.find('textvalue')
                if text is not None and text.text=='BEARING REGION — B':text.text='BETWEEN PILES — B'
        def scaled(value,offset):return f'{offset}+({value})/(1 in)*GfxScale'
        def bars(count,size,x1,x2,y1,y2,offset,color):
            radius=f'Db({size})/(1 in)*GfxScale/2'
            x=f'GfxRowX({count},{scaled(x1,offset)},{scaled(x2,offset)},{radius})'
            y=f'GfxRowY({count},{scaled(y1,".90")},{scaled(y2,".90")},{radius})'
            E.SubElement(canvas,'plot',formula=qualify(f'PlotLines({x},{y})'),linecolor=color,linethickness='1.6')
        for region,offset in [('P','.30'),('B','3.68')]:
            for row in (1,2,3):
                count=f'n_N{row}';size=f'Bar_N{row}';y=f'h-y_N{row}'
                pitch=f'(b-2*(C_s+d_vbar+Db({size})/2))/Max({count}-1,1)'
                if row==1:pitch=f'If(Manual_spacing,SP_detail_N,{pitch})'
                extent=f'Max({count}-1,0)*({pitch})/2'
                bars(count,size,f'b/2-({extent})',f'b/2+({extent})',y,y,offset,'#1766A0')
            for row in (1,2):
                count=f'n_{region}{row}';size=f'Bar_{region}';y=f'y_{region}{row}'
                outer=f'C_s+d_vbar+Db({size})/2'
                pitch=f'(b-2*({outer}))/Max({count}-1,1)'
                if row==1:pitch=f'If(Manual_spacing,SP_detail_{region},{pitch})'
                extent=f'Max({count}-1,0)*({pitch})/2'
                split=f'And(Ready_pile,{y}-Db({size})/2 < Pile_embed+C_pile)' if region=='P' else 'false'
                bars(f'If({split},0,{count})',size,f'b/2-({extent})',f'b/2+({extent})',y,y,offset,'#1766A0')
                if region=='P':
                    left=f'Floor(({count}+1)/2,1)';right=f'{count}-({left})'
                    for n,first,sign in [(left,outer,'+'),(right,f'b-({outer})','-')]:
                        step=f'P_side_span/Max(({n})-1,1)'
                        if row==1:step=f'If(Manual_spacing,SP_detail_P,{step})'
                        last=f'({first}){sign}Max(({n})-1,0)*({step})'
                        bars(f'If({split},{n},0)',size,first,last,y,y,offset,'#1766A0')
            mid=f'(h-y_N1+y_{region}1)/2'
            pitch=f'If(Manual_spacing,SP_skin,(h-y_N1-y_{region}1)/(n_skin+1))'
            half=f'(n_skin-1)*({pitch})/2'
            for x in ('C_s+d_vbar+Db(Bar_skin)/2','b-C_s-d_vbar-Db(Bar_skin)/2'):
                bars('n_skin','Bar_skin',x,x,f'{mid}-({half})',f'{mid}+({half})',offset,'#188565')
        for name,left,right,top,color in [
            ('NotebookPileHead','(b-D_pile)/2','(b+D_pile)/2','Pile_embed','#63758C'),
            ('NotebookPileAllowance','Pile_left-C_pile','Pile_right+C_pile','Pile_embed+C_pile','#BB3E39')]:
            xs=','.join(scaled(x,'.30') for x in (left,right,right,left,left))
            ys=','.join(scaled(y,'.90') for y in ('0 in','0 in',top,top,'0 in'))
            formula=f'PlotLines(If(Ready_pile,[{xs}],[null]),If(Ready_pile,[{ys}],[null]))'
            E.SubElement(canvas,'plot',name=name,formula=qualify(formula),linecolor=color,linethickness='1')
        E.SubElement(canvas,'planecontainer',name='NotebookPileNotice',origin='.15,4.02,0',
            dir='1,0,0',normal='0,0,1',fontfamily='Times New Roman',fontsize='7',textcolor='#BB3E39',
            formula='If(PierCapDesign.Ready_pile,"Pile outline + placement/clearance envelope; hoop stations require detailing","PILE-HEAD DIMENSIONS PENDING — verify cage in notebook")')
