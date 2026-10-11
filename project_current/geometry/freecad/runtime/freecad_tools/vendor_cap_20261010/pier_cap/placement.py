"""One longitudinal layout for actual transverse geometry and calculations.

Continuous bars retain their coordinates along the cap. The intersection of
all entered shapes governs; span supplements conservatively use that same
envelope. This is a geometric fit, not a development or hook congestion design.
"""
import math
from .transverse import bar_shape
from .detailing import required_clear

EPS = 1e-7


def intersect(first, second):
    return [(max(a, c), min(b, d)) for a, b in first for c, d in second
            if max(a, c) <= min(b, d) + EPS]


def subtract(intervals, lo, hi):
    result = []
    for a, b in intervals:
        if hi <= a or lo >= b:
            result.append((a, b))
        else:
            if lo > a: result.append((a, lo))
            if hi < b: result.append((hi, b))
    return result


def capsule_slice(a, b, y, radius):
    """Horizontal slice of a segment swept by a disk (analytic, not sampled)."""
    spans = []
    for x, z in (a, b):
        if abs(y-z) < radius:
            dx = math.sqrt(max(0, radius**2-(y-z)**2))
            spans.append((x-dx, x+dx))
    dx, dy = b[0]-a[0], b[1]-a[1]
    length = math.hypot(dx, dy)
    if length > EPS:
        # The rectangular part of the capsule: perpendicular distance and
        # segment projection both bounded. End disks complete the capsule.
        strip = [(-math.inf, math.inf)]
        if abs(dy) > EPS:
            limits = sorted((a[0]+(dx*(y-a[1])-radius*length)/dy,
                             a[0]+(dx*(y-a[1])+radius*length)/dy))
            strip = intersect(strip, [limits])
        elif abs(y-a[1]) >= radius:
            strip = []
        if abs(dx) > EPS:
            limits = sorted((a[0]-dy*(y-a[1])/dx,
                             a[0]+(length**2-dy*(y-a[1]))/dx))
            strip = intersect(strip, [limits])
        elif not -EPS <= dy*(y-a[1]) <= length**2+EPS:
            strip = []
        spans.extend(strip)
    return (min(s[0] for s in spans), max(s[1] for s in spans)) if spans else None


class Envelope:
    def __init__(self, e):
        self.e = e
        # Identical shapes at many stations need only one cross-section check.
        self.shapes = []
        seen = set()
        for run in e.case['transverse_detail']['runs']:
            shape = bar_shape(e, run)
            key = (run['kind'], shape['diameter'], tuple(sorted(shape['parameters'].items())))
            if key not in seen:
                seen.add(key)
                self.shapes.append((run['kind'], shape))

    def intervals(self, y, diameter, pile=False):
        p = self.e.case['inputs']; rb = diameter/2
        if y-rb < p['C_b']-EPS or y+rb > p['h']-p['C_t']+EPS:
            return []
        spans = [(p['C_s']+rb, p['b']-p['C_s']-rb)]
        for kind, shape in self.shapes:
            if not shape['fit']: return []
            d = shape['diameter']; r = shape['radius']; s = shape['parameters']
            left = p['C_s']+d/2+s['side_inset_in']
            top = p['h']-p['C_t']-d/2
            bottom = p['C_b']+d/2+s['end_raise_in']
            # The rendered arcs use chords. Account for their inward sagitta
            # so even the rendered solid surfaces do not cross at contact.
            q = (d+diameter)/2 + r*(1-math.cos(math.pi/48)) + 1e-6
            lo = left+q
            if y > top-q+EPS: return []
            if r > q and y > top-r:
                lo = max(lo, left+r-math.sqrt(max(0, (r-q)**2-(y-(top-r))**2)))
            if kind == 'hoop':
                if y < bottom+q-EPS: return []
                if r > q and y < bottom+r:
                    lo = max(lo, left+r-math.sqrt(max(0, (r-q)**2-(y-(bottom+r))**2)))
            spans = intersect(spans, [(lo, p['b']-lo)])
            if kind == 'pile_u':
                # Open bottom: only the real legs, bends and independent ends
                # exclude steel. Never add a fictitious bottom closing segment.
                for a, b in zip(shape['points'], shape['points'][1:]):
                    cut = capsule_slice(a, b, y, q)
                    if cut: spans = subtract(spans, *cut)
            if not spans: return []
        if pile and p['Ready_pile']:
            dy = max(0, y-p['Pile_embed']); q = p['C_pile']+rb+1e-6
            if dy < q:
                dx = math.sqrt(max(0, q*q-dy*dy))
                spans = subtract(spans, self.e.value('Pile_left')-dx, self.e.value('Pile_right')+dx)
        return sorted(spans)


def pack(spans, count, minimum, pitch=None):
    """Spread equal bars within allowed intervals, keeping a manual pitch exact."""
    if not count: return []
    if not spans: return None
    if count == 1:
        a, b = max(spans, key=lambda v: v[1]-v[0])
        return [(a+b)/2]
    if pitch is not None:
        if pitch < minimum-EPS: return None
        origins = spans
        for j in range(1, count):
            origins = intersect(origins, [(a-j*pitch, b-j*pitch) for a, b in spans])
        if not origins: return None
        # Center the row as far as its admissible origins allow.
        target = (spans[0][0]+spans[-1][1]-(count-1)*pitch)/2
        origin = min((max(a, min(b, target)) for a, b in origins), key=lambda x: abs(x-target))
        return [origin+j*pitch for j in range(count)]
    def greedy(step):
        xs = []; index = 0; x = spans[0][0]
        for _ in range(count):
            while index < len(spans) and x > spans[index][1]+EPS: index += 1
            if index == len(spans): return None
            x = max(x, spans[index][0]); xs.append(x); x += step
        return xs
    if greedy(minimum) is None: return None
    lo = minimum; hi = (spans[-1][1]-spans[0][0])/(count-1)
    for _ in range(35):
        mid = (lo+hi)/2
        if greedy(mid) is None: hi = mid
        else: lo = mid
    return greedy(lo)


def fill_gaps(spans, count, minimum):
    """Span supplements fill open gaps between fixed continuous bars."""
    if not count: return []
    if not spans: return None
    slots = [[a,b,0] for a,b in spans]
    for _ in range(count):
        available = [s for s in slots if (s[2])*minimum <= s[1]-s[0]+EPS]
        if not available: return None
        slot = max(available,key=lambda s:(s[1]-s[0])/(s[2]+1))
        slot[2] += 1
    xs = []
    for a,b,n in slots:
        if not n: continue
        if n == 1: xs.append((a+b)/2); continue
        pad = max(0,min((b-a-(n-1)*minimum)/2,(b-a)/(n+1)))
        xs.extend(a+pad+j*(b-a-2*pad)/(n-1) for j in range(n))
    return xs if all(b-a>=minimum-EPS for a,b in zip(xs,xs[1:])) else pack(spans,count,minimum)


def actual_layout(e):
    from .model import BAR_DIAMETER
    p = e.case['inputs']; h = p['h']; env = Envelope(e)
    issues = []; values = {}; bars = []
    if not env.shapes:
        return None
    dt = max(s['diameter'] for _, s in env.shapes)
    # Start at the actual straight-side cover. Inward row movement is only
    # made when necessary for shape, pile and same-row clear spacing fit.
    top_base = h-p['C_t']-dt-BAR_DIAMETER[p['Bar_N1']]/2
    bottom_base = p['C_b']+max(s['diameter']+(s['parameters']['end_raise_in'] if k=='hoop' else 0)
                             for k,s in env.shapes)

    def make_row(n, size, y, kind, layer, additional=False, existing=(), strict=True, align=None):
        n = int(n); d = BAR_DIAMETER[size]
        if not n: return []
        from .added_steel import entered_positions,legacy_spacing
        entered=entered_positions(e.case,int(layer[-1])) if additional else None
        if entered is not None:
            # Preserve the user's exact row and leave conflicts visible to the
            # clearance/fit checks. Never translate continuous bars to hide it.
            return [dict(x=x,y=y,diameter=d,kind=kind,layer=layer,bar=int(size),additional=True) for x in entered]
        spans = env.intervals(y, d, pile=kind.startswith('Bottom'))
        minimum = d+(required_clear(e,d) if strict else 1e-5)
        for other in existing:
            # Added bars occupy the same layer even when diameters differ.
            # Respect the actual center-distance clearance to fixed bars.
            q = (d+other['diameter'])/2+(required_clear(e,max(d,other['diameter'])) if strict else 1e-5)
            dy = abs(y-other['y'])
            if dy < q:
                dx = math.sqrt(max(0,q*q-dy*dy))
                spans = subtract(spans, other['x']-dx, other['x']+dx)
        manual = None
        if p['Manual_spacing'] and layer.endswith('1') and (not additional or legacy_spacing(e.case)):
            key = 'SP_detail_B' if additional else 'SP_detail_N' if kind.startswith('Top') else 'SP_detail_P'
            manual = p[key]
        xs = None
        if align is not None and len(align)==n:
            proposed = [v['x'] for v in align]
            if (all(any(a-EPS <= x <= b+EPS for a,b in spans) for x in proposed)
                    and all(b-a >= minimum-EPS for a,b in zip(sorted(proposed),sorted(proposed)[1:]))): xs = proposed
        if xs is None and manual is not None and kind.startswith('Bottom') and p['Ready_pile'] and y-d/2 < p['Pile_embed']+p['C_pile']:
            left = pack(intersect(spans, [(0,p['b']/2)]), (n+1)//2, minimum, manual)
            right = pack(intersect(spans, [(p['b']/2,p['b'])]), n//2, minimum, manual)
            if left is not None and right is not None: xs = left+right
        elif xs is None:
            xs = fill_gaps(spans,n,minimum) if additional and manual is None else pack(spans,n,minimum,manual)
        if xs is None: return None
        return [dict(x=x,y=y,diameter=d,kind=kind,layer=layer,bar=int(size),additional=additional) for x in xs]

    def top_rows(shift, strict=True):
        out = []; row_values = {}; previous = None
        for k in (1,2,3):
            y = top_base-(k-1)*p['s_row']-shift
            row = make_row(p[f'n_N{k}'],p[f'Bar_N{k}'],y,f'Top row {k}',f'Top row {k}',strict=strict,align=previous)
            if row is None: return None
            if row: previous = row
            out.extend(row); row_values[f'y_N{k}'] = h-y
        return out,row_values

    def bottom_rows(shift, strict=True):
        out = []; row_values = {}; previous = None
        for k in (1,2):
            layer = f'Bottom row {k}'
            y = bottom_base+BAR_DIAMETER[p['Bar_P']]/2+(k-1)*p['s_row']+shift
            row = make_row(p[f'n_P{k}'],p['Bar_P'],y,layer,layer,strict=strict,align=previous)
            if row is None: return None
            if row: previous = row
            yb = bottom_base+BAR_DIAMETER[p['Bar_B']]/2+(k-1)*p['s_row']+shift
            extra = make_row(p[f'n_B{k}'],p['Bar_B'],yb,f'Added span row {k}',layer,True,row,strict)
            if extra is None: return None
            out.extend(row+extra); row_values[f'y_P{k}'] = y; row_values[f'y_B{k}'] = yb
        return out,row_values

    def fit(builder, limit):
        # Bounded search followed by refinement; translations keep entered row
        # spacing and counts intact. A failed fit is never converted to PASS.
        for strict in (True, False):
            last = 0.
            for i in range(max(0,math.ceil(limit*8))+1):
                shift = min(i/8, max(0,limit))
                found = builder(shift,strict)
                if found is not None:
                    if shift == 0: return found, 0., strict
                    low, high = last, shift
                    for _ in range(16):
                        mid = (low+high)/2
                        if builder(mid,strict) is None: low = mid
                        else: high = mid
                    found = builder(high,strict)
                    return found, high, strict
                last = shift
        return None, 0., False

    occupied_top = max(k for k in (1,2,3) if p[f'n_N{k}'])
    occupied_bottom = max(k for k in (1,2) if p[f'n_P{k}'] or p[f'n_B{k}'])
    lower_top = top_base-(occupied_top-1)*p['s_row']
    upper_bottom = bottom_base+max(BAR_DIAMETER[p['Bar_P']],BAR_DIAMETER[p['Bar_B']])/2+(occupied_bottom-1)*p['s_row']
    # Do not translate one family through the other. Actual interlayer code
    # clearances still receive their independent checks after positioning.
    available = max(0,lower_top-upper_bottom-2*max(BAR_DIAMETER[p['Bar_P']],BAR_DIAMETER[p['Bar_N1']]))
    top_result,top_shift,top_ok = fit(top_rows,available/2)
    bottom_result,bottom_shift,bottom_ok = fit(bottom_rows,available-top_shift)
    if top_result is None or bottom_result is None:
        # Retain an inspectable, explicitly failed trial rather than dropping
        # bars or changing quantities/shape inputs to manufacture a fit.
        from .model import bar_positions
        fallback = bar_positions(e,'B')
        return {'bars':{'B':fallback,'P':[v for v in fallback if not v['additional']]},
                'values':{},'issues':['Longitudinal steel cannot fit inside the entered hoop/U shapes with the selected counts, row spacing and manual pitches. Revise the cage; displayed reference positions are an unsuccessful trial.'],
                'fitted':False,'top_shift':0.,'bottom_shift':0.}
    for result in (top_result,bottom_result):
        bars.extend(result[0]); values.update(result[1])
    if not top_ok or not bottom_ok:
        issues.append('Longitudinal bars fit the transverse shapes, but the selected same-row clear spacing cannot be met. Review the failed spacing checks.')
    # All side bars on one face share one lateral coordinate; select the
    # coordinate that clears every entered bend and end at their elevations.
    n = int(p['n_skin']); ds = BAR_DIAMETER[p['Bar_skin']]
    bottom = values['y_P1']; top = h-values['y_N1']
    pitch = p['SP_detail_skin'] if p['Manual_spacing'] else (top-bottom)/(n+1)
    ys = [(top+bottom)/2+(j-(n-1)/2)*pitch for j in range(n)]
    spans = [(p['C_s']+ds/2,p['b']/2)]
    for y in ys: spans = intersect(spans,env.intervals(y,ds,pile=True))
    if n and not spans:
        issues.append('Side steel cannot fit inside all entered hoop/U shapes at the selected elevations. Revise side count, spacing or transverse geometry.')
    left = spans[0][0] if spans else p['C_s']+dt+ds/2
    for x in (left,p['b']-left):
        for y in ys: bars.append(dict(x=x,y=y,diameter=ds,kind='Skin',layer='Skin',bar=int(p['Bar_skin']),additional=False))
    regions = {'B':bars,'P':[v for v in bars if not v['additional']]}
    from .added_steel import fit_problems
    from .detailing import row_spacing
    issues.extend(fit_problems(e,bars))
    for z, label in [('N','Top row 1'),('P','Bottom row 1'),('B','Bottom row 1')]:
        row = [v for v in regions['B' if z=='B' else 'P'] if v['layer']==label]
        spacing = row_spacing(e,row,at_pile=z!='B')['pitch_in']
        values['SP_'+z] = values['SP_'+z+'_auto'] = spacing
    values['SP_skin'] = values['SP_skin_auto'] = pitch
    bottom_x = sorted(v['x'] for v in regions['P'] if v['layer']=='Bottom row 1')
    left_x = [x for x in bottom_x if x <= p['b']/2]
    right_x = [x for x in bottom_x if x > p['b']/2]
    values['P_center_gap'] = min(right_x)-max(left_x) if left_x and right_x else 0.
    values['P_side_span'] = max((xs[-1]-xs[0] if xs else 0.) for xs in (left_x,right_x))
    for name,xs in [('left',left_x),('right',right_x)]:
        values['P_pitch_'+name] = max((b-a for a,b in zip(xs,xs[1:])),default=0.)
    # Legacy U-leg counts still have no resolved position and remain a detail
    # issue. Their existing nominal depth follows the translated bottom family.
    values['y_U'] = bottom_base+BAR_DIAMETER[p['Bar_U']]/2+bottom_shift
    return {'bars':regions,'values':values,'issues':issues,'fitted':not issues,
            'top_shift':top_shift,'bottom_shift':bottom_shift}
