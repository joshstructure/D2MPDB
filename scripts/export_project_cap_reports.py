"""Re-export the project cap design reports from their selected cases.

    .venv\\Scripts\\python.exe scripts\\export_project_cap_reports.py --date 10-17
    .venv\\Scripts\\python.exe scripts\\export_project_cap_reports.py --check

Each report is written beside its `selected_case.json` as `<name> <m-d>.html`
by `pier_cap.calculation_report.write_calculation_report`. The selected cases
are only read. `--check` verifies that the registered reports embed the
corrected equation schematics and the exact saved case.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CAP_DESIGN = ROOT / 'project_current' / 'cap_design'
REPORTS = (
    ('PIER-REPORT', 'PIER-CASE', 'pier', 'Pier Cap Design'),
    ('EB-REPORT', 'EB-CASE', 'end_bents', 'End Bent 1 Cap Design'),
    ('EB2-REPORT', 'EB2-CASE', 'end_bent_2', 'End Bent 2 Cap Design'),
)

FIGURE = re.compile(r'<figure class="equation-schematic" data-equation="([^"]*)" data-concept="([^"]*)"[^>]*>(.*?)</figure>', re.S)
# Concept routing and parameters from the schematic correction (commit 5cce568), limited
# to equations these actual-cage reports publish (Sw_G, tstress and K_limit are not among them).
CONCEPTS = {'beta_1': 'flexure', 'alpha_1': 'flexure', 'Mcr': 'gross', 'P_pitch_left': 'spacing',
            'P_center_gap': 'spacing', 'Pile_left': 'spacing', 'S_leg': 'legs', 'Chk_drawn_hoop_legs_G': 'legs'}
LABELS = {'L_cap': ('D_pile', 'E_CL'), 'P_center_gap': ('Pile_left',)}


def schematic_problems(markup: str) -> list[str]:
    """Return the ways a report's equation schematics differ from the corrected set."""
    figures = FIGURE.findall(markup)
    if not figures:
        return ['no equation schematics']
    problems = []
    by_name: dict[str, list[tuple[str, str]]] = {}
    for name, concept, body in figures:
        by_name.setdefault(html.unescape(name), []).append((concept, body))
        if '<script' in body or 'href=' in body:
            problems.append(f'{name}: script or link inside the sketch')
        if 'role="img"' not in body or 'aria-label="' not in body:
            problems.append(f'{name}: sketch is not an accessible image')
    for name, concept in CONCEPTS.items():
        found = by_name.get(name)
        if not found:
            problems.append(f'{name}: no sketch')
        elif any(c != concept for c, _ in found):
            problems.append(f'{name}: data-concept {sorted({c for c, _ in found})} instead of {concept!r}')
    for name, labels in LABELS.items():
        found = by_name.get(name)
        if not found:
            problems.append(f'{name}: no sketch')
            continue
        text = ' '.join(re.sub(r'<[^>]+>', ' ', body) for _, body in found)
        problems += [f'{name}: sketch lacks {label}' for label in labels if label not in html.unescape(text)]
    return problems


def embedded_case(markup: str) -> dict:
    """The single saved case a report carries in its provenance section."""
    text = html.unescape(markup)
    decoder = json.JSONDecoder()
    cases = []
    for match in re.finditer(r'\{\s*"schema_version"\s*:', text):
        try:
            case, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(case, dict) and 'inputs' in case and 'analysis' in case:
            cases.append(case)
    if len(cases) != 1:
        raise ValueError(f'Expected one embedded cap case; found {len(cases)}.')
    return cases[0]


def registered_reports() -> dict[str, tuple[Path, Path]]:
    """Report and case paths from the source register, keyed by report source id."""
    with (ROOT / 'project_current' / 'source_register.csv').open(newline='', encoding='utf-8-sig') as f:
        paths = {row['source_id']: ROOT / row['path'] for row in csv.DictReader(f)}
    return {report: (paths[report], paths[case]) for report, case, _, _ in REPORTS}


def export(date_label: str, root: Path = CAP_DESIGN) -> list[Path]:
    from pier_cap.calculation_report import write_calculation_report
    from pier_cap.io import load_case

    written = []
    for _, _, folder, title in REPORTS:
        source = root / folder / 'selected_case.json'
        saved = json.loads(source.read_text(encoding='utf-8-sig'))
        case = load_case(source)
        if case != saved:
            raise ValueError(f'{source} changes when loaded; the report would not carry the saved case.')
        written.append(write_calculation_report(case, root / folder / f'{title} {date_label}.html'))
    return written


def check() -> list[str]:
    problems = []
    for report_id, (report, case) in registered_reports().items():
        markup = report.read_text(encoding='utf-8')
        problems += [f'{report_id}: {p}' for p in schematic_problems(markup)]
        if embedded_case(markup) != json.loads(case.read_text(encoding='utf-8-sig')):
            problems.append(f'{report_id}: embedded case differs from {case.name}')
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--date', help='m-d suffix for the new report names, for example 10-17')
    parser.add_argument('--check', action='store_true', help='verify the registered reports instead of exporting')
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding='utf-8')
    if args.check:
        problems = check()
        print('\n'.join(problems) if problems else 'Registered cap reports carry the corrected schematics and their saved cases.')
        return 1 if problems else 0
    if not args.date:
        parser.error('--date is required to export')
    for path in export(args.date):
        print(f'Wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
