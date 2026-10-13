"""Independent preview of the same native sketch geometry; not native review."""
from pathlib import Path
import json,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from verify_module import TASK,evaluate,display

for spec in json.loads((TASK/'sketches.json').read_text()):
    fig,ax=plt.subplots(figsize=(9,spec['height']*9/6.5),layout='constrained')
    ax.set_xlim(0,6.5);ax.set_ylim(0,spec['height']);ax.set_aspect('equal');ax.axis('off')
    scale=evaluate(spec['scale']).v;ox=float(spec['ox']);oy=float(spec['oy'])
    for line in spec['lines']:
        points=[(ox+evaluate(x).v/12*scale,oy+evaluate(y).v/12*scale) for x,y in line['points']]
        ax.plot([x for x,y in points],[y for x,y in points],color=line['color'],lw=line['width'])
    for label in spec['labels']:
        text=display(label['formula']) if label['formula'] else label['text']
        ax.text(label['x'],label['y'],text,color=label['color'],fontsize=label['size'],va='bottom',fontfamily='serif',bbox={'facecolor':'white','edgecolor':'none','pad':.1})
    fig.savefig(TASK/f'preview-{spec["name"]}.png',dpi=140);plt.close(fig)
print('Rendered three independent geometry previews.')
