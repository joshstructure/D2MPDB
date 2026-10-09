"""Stable references shared by notebook views and their exported copies."""
from functools import wraps
import html
import re


FIGURES = {
    'pile_heads': (1, 'Pile-head loads'), 'pile_profiles': (2, 'Pile profiles'),
    'pile_section': (3, 'Pile section'), 'pile_trials': (4, 'Minimum-tip trials'),
    'cap_forces': (5, 'Cap force diagrams'), 'cap_dimensions': (6, 'Cap dimensions'),
    'cap_section_pile': (7, 'Cap cross section at pile'), 'cap_section_span': (8, 'Cap cross section between piles'),
    'cap_plan': (9, 'Reinforcement plan'), 'cap_elevation': (10, 'Reinforcement elevation'),
    'cap_hoops': (11, 'Hoop arrangement'), 'pile_embedment': (12, 'Pile embedment schematic'),
    'cap_3d': (13, '3D reinforcement cage'), 'cap_results': (14, 'Cap demand and resistance'),
    'actual_results': (15, 'Actual cage demand and resistance'), 'cap_ratios': (16, 'Cap check ratios'),
    'cap_service': (17, 'Optional service and fatigue checks'), 'cap_alternatives': (18, 'Steel alternatives'),
    'section_heatmap': (19, 'Section study'), 'section_cost': (20, 'Section costs'),
    'section_pareto': (21, 'Concrete and steel tradeoff'), 'cap_snapshot': (22, 'Cap snapshot'),
    'section_snapshot': (23, 'Section study snapshot'),
    'study_section_pile': (24, 'Candidate cross section at pile'), 'study_section_span': (25, 'Candidate cross section between piles'),
    'study_results': (26, 'Candidate demand and resistance'),
}
TABLES = {
    'pile_summary': (1, 'Pile result envelopes'), 'pile_properties': (2, 'Pile section properties'),
    'pile_elastic': (3, 'Elastic stress checks'), 'pile_cracking': (4, 'Reported cracking-strain checks'),
    'pile_stresses': (5, 'Reported material stress extrema'), 'minimum_tip': (6, 'Minimum-tip criteria'),
    'profile_issues': (7, 'Profiles needing review'), 'crossings': (8, 'Crossing locations for Figure 2'),
    'trial_summary': (9, 'Trial calculation summary'), 'trial_rows': (10, 'Displacement-change trials'),
    'handoff_section': (11, 'Handoff pile information'), 'handoff_tip': (12, 'Handoff minimum-tip criteria'),
    'handoff_loads': (13, 'Handoff pile-head loads'), 'cap_dimensions': (14, 'Cap dimensions'),
    'pile_stations': (15, 'Pile center and face stations'), 'cap_configuration': (16, 'Current cap configuration'),
    'clear_spacing': (17, 'Bar clear spacing'), 'hoop_basis': (18, 'Hoop design inputs'),
    'hoop_spacing': (19, 'Hoop spacing checks'), 'cap_checks': (20, 'Cap check register'),
    'hoop_schedule': (21, 'Transverse bar runs'), 'strength_loads': (22, 'Strength load breakdown'),
    'strength_sources': (23, 'Strength input sources'), 'xml_geometry': (24, 'Imported geometry and materials'),
    'xml_forces': (25, 'Imported force envelopes'), 'live_equations': (26, 'Live equations'),
    'steel_alternatives': (27, 'Steel alternatives'), 'section_costs': (28, 'Section cost comparison'),
    'study_spacing': (29, 'Candidate hoop spacing'), 'study_checks': (30, 'Candidate check register'),
    'other_crossings': (31, 'Crossing locations outside the current plot selection'),
    'wind_scope': (32, 'Wind combinations for the crossing check'),
}


def table_reference(key):
    number, title = TABLES[key]
    return f'Table {number} — {title}'


def table_caption(key):
    return '<caption data-reference="'+html.escape(key)+'" style="caption-side:top;text-align:left;font-weight:700;padding:8px 0;color:#213649">'+html.escape(table_reference(key))+'</caption>'


def number_tables(markup, *keys, report=False):
    """Add captions only to unlabeled tables, without global render counters."""
    keys = iter(keys)
    count = 0
    def add(match):
        nonlocal count
        if report:
            count += 1
            caption = f'<caption data-reference="report-{count}" style="caption-side:top;text-align:left;font-weight:700;padding:8px 0">Table R{count} — Calculation detail</caption>'
        else:
            caption = table_caption(next(keys))
        return match.group()+caption
    return re.sub(r'<table\b[^>]*>(?!\s*<caption\b)', add, markup)


def numbered_tables(*keys):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            return number_tables(function(*args, **kwargs), *keys)
        return wrapped
    return decorate


def numbered_figure(key):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            selected = key(*args, **kwargs) if callable(key) else key
            return label_figure(function(*args, **kwargs), selected)
        return wrapped
    return decorate


def label_figure(fig, key):
    number, fallback = FIGURES[key]
    reference = f'Figure {number}'
    def title(text): return reference+' — '+re.sub(r'^Figure \d+ — ', '', text or fallback)
    if hasattr(fig, 'update_layout'):
        if not fig.layout.title.text:
            fig.update_layout(margin_t=max(fig.layout.margin.t or 0, 85))
        fig.update_layout(title_text=title(fig.layout.title.text), meta=dict(fig.layout.meta or {}, reference=reference))
        # Dropdowns can replace titles without invoking Python again.
        for menu in fig.layout.updatemenus:
            for button in menu.buttons:
                if button.method=='update' and len(button.args or ())>1:
                    layout = button.args[1]
                    if 'title.text' in layout: layout['title.text'] = title(layout['title.text'])
    else:
        fig.suptitle(title(fallback))
    return fig


def relabel_table(markup, old_key, new_key):
    return re.sub(r'<caption data-reference="'+re.escape(old_key)+r'"[^>]*>.*?</caption>',
                  lambda _: table_caption(new_key), markup)
