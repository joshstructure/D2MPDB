"""Bounded width/depth studies with explicit force provenance and material tradeoffs.

Fixed-force screening never fabricates a matching analysis. Every exported or
selected case retains the analysis geometry supplied with its force values.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import csv
import hashlib
import json
import math

from .model import GEOMETRY, analysis_match, evaluate, set_inputs, validate_case
from .optimizer import SearchConfig, search, sensitivity_search, candidate_case, filter_candidates
from .io import write_case

FORCE_INPUTS = {
    'Vu_G', 'Vu_L', 'Tu', 'Ready_III', 'Ready_fatigue',
    *(prefix + z for prefix in ('Mu_', 'MI_', 'MIII_', 'MDL_', 'DMLL_') for z in 'NPB'),
}
ENGINE_SHA = hashlib.sha256(b''.join(
    (Path(__file__).parent / name).read_bytes() for name in (
        'engine.py', 'model.py', 'optimizer.py', 'sections.py', 'data/c005_formulas.json', 'data/dc_ratio_spec.json')
)).hexdigest()


@dataclass(frozen=True)
class SectionGrid:
    widths: tuple = (44, 48, 52)
    depths: tuple = (36, 42, 48, 54, 60)
    force_mode: str = 'fixed'
    max_total_cases: int = 100000
    minimum_width_in: float = 0
    minimum_depth_in: float = 0


@dataclass(frozen=True)
class CostRates:
    concrete_per_yd3: float = 0
    steel_per_lb: float = 0
    form_per_ft2: float = 0

    def validate(self):
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0
               for v in asdict(self).values()) or not any(asdict(self).values()):
            raise ValueError('Enter nonnegative comparison rates, with at least one positive rate. Zero excludes that cost item.')
        return self


@dataclass
class SectionPoint:
    width: float
    depth: float
    state: str
    reason: str = ''
    result: object = None
    concrete_yd3: float = 0
    form_ft2: float = 0
    cache_hit: bool = False


@dataclass
class SectionStudyResult:
    grid: dict
    steel_config: dict
    base_case: dict
    points: list
    evaluated: int
    new_evaluations: int
    total: int
    exhaustive: bool
    elapsed: float
    minimum_width_in: float
    engine_sha: str = ENGINE_SHA


class SectionCache:
    """In-memory cache scoped to exact case, search, force mode and engine inputs."""
    def __init__(self):
        self.entries = {}

    @staticmethod
    def key(case, config, mode):
        data = {'case': case, 'config': asdict(config), 'mode': mode, 'engine': ENGINE_SHA}
        return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def get(self, key):
        return deepcopy(self.entries.get(key))

    def put(self, key, value):
        self.entries[key] = deepcopy(value)


def dimension_values(start, stop, step):
    """Inclusive regular grid; reject accidental partial endpoints or huge grids."""
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in (start, stop, step)):
        raise ValueError('Dimension bounds and steps must be finite numbers.')
    if start <= 0 or stop < start or step <= 0:
        raise ValueError('Use positive dimensions/steps and an upper bound at least the lower bound.')
    count = (stop - start) / step
    if not math.isclose(count, round(count), abs_tol=1e-8) or count > 224:
        raise ValueError('The upper bound must fall on the step grid; at most 225 values are allowed.')
    return tuple(round(start + i * step, 8) for i in range(round(count) + 1))


def _validate_grid(grid):
    if grid.force_mode not in ('fixed', 'matched'):
        raise ValueError('Choose fixed-force sensitivity or analysis-matched cases.')
    for values in (grid.widths, grid.depths):
        if not values or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in values):
            raise ValueError('Provide finite, positive widths and depths.')
        if list(values) != sorted(set(values)):
            raise ValueError('Widths and depths must be unique and increasing.')
    if len(grid.widths) * len(grid.depths) > 225:
        raise ValueError('Use at most 225 geometry points per study; refine a smaller region afterward.')
    if type(grid.max_total_cases) is not int or not 1 <= grid.max_total_cases <= 500000:
        raise ValueError('The total study budget must be between 1 and 500,000 candidate evaluations.')
    for x in (grid.minimum_width_in, grid.minimum_depth_in):
        if isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or x < 0:
            raise ValueError('Project minimum dimensions must be finite and nonnegative.')


def _steel_input(name):
    return name.startswith(('Bar_', 'n_', 'SP_detail_')) or name in ('s_G', 's_L', 's_row', 'Manual_spacing', 'S_leg_detail')


def _analysis_case(base, width, depth, analyzed_cases):
    """Use forces and readiness from a complete, geometry-matched saved case."""
    matches = []
    for candidate in analyzed_cases:
        p = candidate['inputs']
        if all(math.isclose(p[k], v, abs_tol=1e-6, rel_tol=0) for k, v in (('b', width), ('h', depth))):
            if analysis_match(candidate):
                raise ValueError('The supplied case at this section has stale analysis geometry.')
            if candidate.get('section_study', {}).get('force_mode') == 'fixed':
                raise ValueError('A fixed-force study export is not a new analyzed case. Import actual analysis forces first.')
            different = [k for k, value in base['inputs'].items()
                         if k not in FORCE_INPUTS | {'b', 'h'} and not _steel_input(k) and p[k] != value]
            if different:
                raise ValueError('Analyzed case differs in other project inputs: ' + ', '.join(different))
            matches.append(candidate)
    if not matches:
        return None
    if len(matches) > 1:
        # Identical uploads are harmless; distinct force/source records are not chosen silently.
        signatures = {json.dumps({'forces': {k: c['inputs'][k] for k in FORCE_INPUTS}, 'analysis': c['analysis']}, sort_keys=True) for c in matches}
        if len(signatures) > 1:
            raise ValueError('Multiple different analyses exist for this section. Keep only the intended case in the analysis library.')
    source = matches[0]
    case = set_inputs(base, b=width, h=depth, **{k: source['inputs'][k] for k in FORCE_INPUTS})
    case['analysis'] = deepcopy(source['analysis'])
    case.pop('section_study', None)
    return case


def run_section_study(base_case, grid=None, steel_config=None, *, analyzed_cases=(), cache=None, progress=None):
    grid = grid or SectionGrid()
    steel = steel_config or SearchConfig()
    _validate_grid(grid)
    validate_case(base_case)
    if set(analysis_match(base_case)) - {'b', 'h'}:
        raise ValueError('The pile layout has changed. Supply matching pile-layout forces before studying cap sections.')
    # Validate the steel grid once even if every geometry is rejected before enumeration.
    grids = (steel.main_bars, steel.top_counts, steel.bottom_counts, steel.hoop_bars,
             steel.hoop_spacings, steel.skin_bars, steel.skin_counts)
    if any(not values for values in grids):
        raise ValueError('Select at least one value in every steel search list.')
    if type(steel.max_cases) is not int or not 1 <= steel.max_cases <= 100000:
        raise ValueError('Per-section steel limit must be between 1 and 100,000.')
    total_per_section = math.prod(len(values) for values in grids)
    initial = evaluate(base_case)
    # E_detail / E_end describe the longitudinal cap ends. An imported longer
    # cantilever must not silently enlarge the transverse pile-edge screen.
    side_allowance = base_case['inputs']['E_clear'] + initial.value('Tol_pile')
    minimum_width = max(grid.minimum_width_in, base_case['inputs']['D_pile'] + 2 * side_allowance)
    length_ft = initial.value('L_cap') / 12
    library = list(analyzed_cases)
    for case in library:
        validate_case(case)
    # The current case supplies exactly its own source section, never the rest of the grid.
    has_current_section = any(all(math.isclose(c['inputs'][k], base_case['inputs'][k], rel_tol=0, abs_tol=1e-6)
                                  for k in ('b', 'h')) for c in library)
    if not has_current_section and not analysis_match(base_case) and base_case.get('section_study', {}).get('force_mode') != 'fixed':
        library.append(base_case)
    cache = cache if cache is not None else SectionCache()
    points = []
    evaluated = new_evaluations = 0
    started = perf_counter()
    total = len(grid.widths) * len(grid.depths) * total_per_section
    for depth in grid.depths:
        for width in grid.widths:
            point = SectionPoint(width, depth, 'NOT RUN')
            point.concrete_yd3 = width / 12 * depth / 12 * length_ft / 27
            # Side faces, ends and soffit only; no top, falsework or pile deductions.
            point.form_ft2 = 2 * length_ft * depth / 12 + length_ft * width / 12 + 2 * width * depth / 144
            points.append(point)
            if width < minimum_width - 1e-9 or depth < grid.minimum_depth_in - 1e-9:
                point.state = 'GEOMETRY SCREEN'
                point.reason = f'Requires width ≥ {minimum_width:g} in and entered project depth ≥ {grid.minimum_depth_in:g} in.'
            elif evaluated >= grid.max_total_cases:
                point.reason = 'Total candidate budget reached. This section was not evaluated.'
            else:
                try:
                    if grid.force_mode == 'fixed':
                        case = set_inputs(base_case, b=width, h=depth)
                    else:
                        case = _analysis_case(base_case, width, depth, library)
                    if case is None:
                        point.state = 'NEEDS ANALYSIS'
                        point.reason = 'No geometry-matched force case supplied. No fixed-force fallback was used.'
                    else:
                        limited = replace(steel, max_cases=min(steel.max_cases, grid.max_total_cases - evaluated))
                        key = cache.key(case, limited, grid.force_mode)
                        result = cache.get(key)
                        point.cache_hit = result is not None
                        if result is None:
                            def inner(n, maximum):
                                if progress:
                                    progress(len(points) - 1, len(grid.widths) * len(grid.depths), evaluated + n, total)
                            result = (sensitivity_search if grid.force_mode == 'fixed' else search)(case, limited, inner)
                            cache.put(key, result)
                            new_evaluations += result.evaluated
                        point.result = result
                        evaluated += result.evaluated
                        point.state = 'EVALUATED' if result.exhaustive else 'PARTIAL'
                        point.reason = 'Single outer hoop; available sectional checks and trial cage screen only.'
                except (ValueError, ZeroDivisionError, OverflowError) as exc:
                    point.state = 'INPUT / ANALYSIS ERROR'
                    point.reason = str(exc)
            if progress:
                progress(len(points), len(grid.widths) * len(grid.depths), evaluated, total)
    exhaustive = all(p.state == 'GEOMETRY SCREEN' or (p.result is not None and p.result.exhaustive) for p in points)
    return SectionStudyResult(asdict(grid), asdict(steel), deepcopy(base_case), points, evaluated, new_evaluations,
                              total, exhaustive, perf_counter() - started, minimum_width)


def comparison_costs(concrete_yd3, steel_lb, form_ft2, rates):
    """Gross comparison quantities at entered rates, in one user-chosen currency."""
    rates.validate()
    parts = {'concrete_cost': concrete_yd3 * rates.concrete_per_yd3,
             'steel_cost': steel_lb * rates.steel_per_lb,
             'form_cost': form_ft2 * rates.form_per_ft2}
    parts['estimated_cost'] = sum(parts.values())
    if not math.isfinite(parts['estimated_cost']):
        raise ValueError('These rates overflow the cost calculation. Enter finite comparison costs.')
    return parts


def ranked_cost_rows(rows):
    """All target-matching priced sections; IDs remain the original study IDs."""
    return sorted((r for r in rows if r['matches'] and r['estimated_cost'] is not None),
                  key=lambda r: (r['estimated_cost'], r['steel_lb'], r['point_id']))


def cost_gap(cost, baseline):
    difference = cost - baseline
    if math.isclose(cost, baseline, rel_tol=1e-12, abs_tol=1e-9):
        difference = 0.0
    percent = difference / baseline * 100 if baseline > 0 else (0.0 if difference == 0 else None)
    return difference, percent


def section_rows(study, target=.9, rates=None):
    """Cheapest gross-steel target match per section; no new evaluations."""
    if isinstance(target, bool) or not isinstance(target, (float, int)) or not math.isfinite(target) or not 0 < target <= 1:
        raise ValueError('Strength target must be greater than zero and at most one.')
    if rates is not None:
        rates.validate()
    rows = []
    for i, p in enumerate(study.points):
        ids = filter_candidates(p.result, target, 'strength', 'Least steel') if p.result else []
        chosen = p.result.candidates[ids[0]] if ids else None
        costs = dict.fromkeys(('concrete_cost', 'steel_cost', 'form_cost', 'estimated_cost'))
        if chosen is not None and rates is not None:
            costs = comparison_costs(p.concrete_yd3, chosen.weight_lb, p.form_ft2, rates)
        rows.append({'point_id': i, 'width_in': p.width, 'depth_in': p.depth,
                     'state': p.state, 'reason': p.reason, 'matches': len(ids), 'candidate_ids': ids,
                     'candidate_id': ids[0] if ids else None, 'steel_lb': chosen.weight_lb if chosen else None,
                     'strength_dc': chosen.strength_dc if chosen else None, 'all_check_ratio': chosen.max_dc if chosen else None,
                     'layout': chosen.label if chosen else '', 'complexity': chosen.complexity if chosen else None,
                     'concrete_yd3': p.concrete_yd3, 'form_ft2': p.form_ft2, **costs,
                     'cost_rank': None, 'cost_difference': None, 'cost_premium_pct': None, 'lowest_cost': False,
                     'force_mode': study.grid['force_mode'], 'pareto': False})
    priced = ranked_cost_rows(rows)
    for index, row in enumerate(priced):
        row['cost_difference'], row['cost_premium_pct'] = cost_gap(row['estimated_cost'], priced[0]['estimated_cost'])
        row['lowest_cost'] = row['cost_difference'] == 0
        tied = index and cost_gap(row['estimated_cost'], priced[index - 1]['estimated_cost'])[0] == 0
        row['cost_rank'] = priced[index - 1]['cost_rank'] if tied else index + 1
    # Material frontier among explored, target-matching results. Same-material ties are retained.
    feasible = sorted((r for r in rows if r['matches']), key=lambda r: (r['concrete_yd3'], r['steel_lb']))
    best_steel = math.inf
    previous = None
    for row in feasible:
        pair = (row['concrete_yd3'], row['steel_lb'])
        tied = previous is not None and all(math.isclose(a, b, rel_tol=0, abs_tol=1e-9) for a, b in zip(pair, previous))
        row['pareto'] = row['steel_lb'] < best_steel - 1e-9 or tied
        if row['pareto']:
            best_steel = min(best_steel, row['steel_lb'])
            previous = pair
    return rows


def selected_section_case(study, point_id, candidate_id):
    if type(point_id) is not int or not 0 <= point_id < len(study.points):
        raise IndexError('Section selection is outside this study.')
    point = study.points[point_id]
    if point.result is None:
        raise ValueError('This section has no calculated reinforcement candidates.')
    case = candidate_case(point.result, candidate_id)
    case['name'] = f'{study.base_case["name"]} · {point.width:g} × {point.depth:g} in'
    case['section_study'] = {'force_mode': study.grid['force_mode'], 'point_id': point_id,
                             'candidate_id': candidate_id, 'engine_sha': study.engine_sha,
                             'note': 'Fixed-force results are sensitivities, not new analysis forces.' if study.grid['force_mode'] == 'fixed'
                                     else 'Force-source geometry matches; full design review and pending checks remain.'}
    return case


def export_section_study(study, root='exports', *, target=.9, rates=None, selected=None):
    rows = section_rows(study, target, rates)
    chosen = selected_section_case(study, *selected) if selected is not None else None
    path = Path(root) / datetime.now(timezone.utc).strftime('section-study-%Y%m%d-%H%M%S-%f')
    path.mkdir(parents=True, exist_ok=False)
    columns = [k for k in rows[0] if k != 'candidate_ids']
    with (path / 'sections.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    with (path / 'all_section_cages.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Point ID (zero-based)', 'Candidate ID (zero-based)', 'Width (in)', 'Depth (in)', 'Layout',
                         'Gross steel (lb)', 'Strength D/C', 'All-check utilization', 'Meets target', 'Force mode', 'Analysis ID'])
        for i, point in enumerate(study.points):
            if point.result:
                for j, c in enumerate(point.result.candidates):
                    writer.writerow([i, j, point.width, point.depth, c.label, c.weight_lb, c.strength_dc, c.max_dc,
                                     c.strength_dc <= target + 1e-12, study.grid['force_mode'], point.result.base_case['analysis']['id']])
    requests = []
    for row, point in zip(rows, study.points):
        if point.state == 'GEOMETRY SCREEN':
            continue
        case = point.result.base_case if point.result else set_inputs(study.base_case, b=point.width, h=point.depth)
        if study.grid['force_mode'] == 'fixed' or point.result is None:
            requests.append({'point_id': row['point_id'], 'geometry': {k: case['inputs'][k] for k in GEOMETRY},
                             'reason': 'Supply forces from this geometry, including self-weight/stiffness effects and required load combinations.'})
    (path / 'analysis_requests.json').write_text(json.dumps(requests, indent=2), encoding='utf-8')
    manifest = {'grid': study.grid, 'steel_config': study.steel_config, 'base_case': study.base_case,
                'target': target, 'rates': asdict(rates) if rates else None, 'selected': selected,
                'evaluated': study.evaluated, 'new_evaluations': study.new_evaluations, 'total': study.total,
                'exhaustive': study.exhaustive, 'elapsed': study.elapsed, 'engine_sha': study.engine_sha,
                'analysis_records': [{'point_id': i, 'analysis': p.result.base_case['analysis'],
                                     'forces': {k: p.result.base_case['inputs'][k] for k in FORCE_INPUTS}}
                                    for i, p in enumerate(study.points) if p.result],
                'limitations': 'Bounded single-outer-hoop family. Fixed mode holds all forces constant and does not update cap self-weight or stiffness in analysis. Matched mode checks declared geometry; it is not independent verification of the force model. Steel excludes hooks/laps/waste; concrete is gross; forms include sides, ends and soffit. Pending checks remain pending. Pareto frontier covers only explored candidates.'}
    (path / 'study.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    if chosen:
        write_case(chosen, path / 'selected_case.json')
    return path
