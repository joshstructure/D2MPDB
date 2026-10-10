"""FDOT January 2026 cap bar-size and exterior concrete-cover policy checks."""
from copy import deepcopy

EXPOSURES = {'unknown': 'Unconfirmed', 'slight': 'Slightly aggressive',
             'moderate': 'Moderately aggressive', 'extreme': 'Extremely aggressive'}
SURFACES = {'unknown': 'Unconfirmed', 'formed': 'Formed · outside water',
            'earth_water': 'Cast against earth / water contact'}
FACES = (('top', 'Top', 'C_t'), ('bottom', 'Bottom', 'C_b'), ('sides', 'Sides / ends', 'C_s'))


def settings(case):
    result = {'exposure': 'unknown', **{face: 'unknown' for face, _, _ in FACES}}
    saved = case.get('fdot_detailing', {})
    if not isinstance(saved, dict):
        raise ValueError('FDOT detailing settings must be an object.')
    result.update(deepcopy(saved))
    return result


def validate_settings(case):
    s = settings(case)
    for key, options in [('exposure', EXPOSURES), *((f, SURFACES) for f, _, _ in FACES)]:
        if s[key] not in options:
            raise ValueError('Unsupported FDOT detailing setting: '+key)


def required_cover(exposure, surface):
    """SDG Table 1.4.2-1: exterior substructure, ordinary carbon reinforcement."""
    if 'unknown' in (exposure, surface):
        return None
    return (4.5 if exposure == 'extreme' else 4.) if surface == 'earth_water' else (4. if exposure == 'extreme' else 3.)


def detailing_checks(e):
    from .model import Check, BAR_DIAMETER, bar_positions
    from .transverse import enabled
    from .check_working import record
    p = e.case['inputs']; s = settings(e.case); checks = []
    groups = {}
    for bar in bar_positions(e, 'B'):
        groups[(bar['kind'], bar['bar'])] = bar['bar']
    inventory = [('main_'+str(i), label, bar, 11) for i, ((label, bar), _) in enumerate(groups.items())]
    if enabled(e.case):
        inventory += [('run_'+r['id'], r['id']+' · '+('pile U-bar' if r['kind'] == 'pile_u' else 'hoop'), r['bar'], 6)
                      for r in e.case['transverse_detail']['runs']]
    else:
        inventory.append(('reference_hoop', 'Uniform hoop', p['Bar_v'], 6))
    for key, label, bar, maximum in inventory:
        diameter = BAR_DIAMETER[bar]; low = BAR_DIAMETER[4]; high = BAR_DIAMETER[maximum]
        ratio = max(low/diameter, diameter/high)
        check = Check('Chk_fdot_bar_'+key, 'FDOT bar size · '+label, 'PASS' if ratio <= 1 else 'FAIL', 'N/A',
                      f'FDOT SDM 4.3.11: cast-in-place cap bars require #4 minimum; '
                      f'{"stirrups" if maximum == 6 else "main bars"} permit #{maximum} maximum. Entered #{bar}. '
                      'This is a permitted-size check, not a strength utilization.')
        record(check, 'FDOT bar diameter limits', [('bar designation', '#'+str(int(bar)), ''),
               ('provided diameter d_b', diameter, 'in'), ('minimum diameter d_min (#4)', low, 'in'),
               (f'maximum diameter d_max (#{maximum})', high, 'in')])
        checks.append(check)
    for face, label, key in FACES:
        required = required_cover(s['exposure'], s[face]); provided = p[key]
        status = 'PENDING' if required is None else 'PASS' if provided >= required else 'FAIL'
        ratio = 'PENDING' if required is None else required/provided
        check = Check('Chk_fdot_cover_'+face, 'FDOT clear cover · '+label, status, ratio,
                      'FDOT SDG Table 1.4.2-1, exterior substructure surfaces with ordinary carbon reinforcement. '
                      'Compares entered clear cover to the policy minimum; cage-fit checks remain applicable. '
                      'The sides / ends setting must cover the most severe condition on those faces.'
                      + (' Select environmental classification and face condition under Geometry → FDOT detailing.' if required is None else ''))
        record(check, 'FDOT minimum concrete cover', [('environmental classification', EXPOSURES[s['exposure']], ''),
               ('face condition', SURFACES[s[face]], ''), ('provided clear cover c', provided, 'in'),
               ('required cover c_req', 'Unconfirmed' if required is None else required, '' if required is None else 'in')])
        checks.append(check)
    return checks


class FDOTDetailingPanel:
    def __init__(self, owner):
        import ipywidgets as W
        self.owner = owner; self.busy = False; self.controls = {}; self.widgets = []
        s = settings(owner.case)
        for key, label, options in [('exposure', 'Environment', EXPOSURES), *((f, label, SURFACES) for f, label, _ in FACES)]:
            control = W.Dropdown(description=label, options=[(v, k) for k, v in options.items()], value=s[key],
                                 style={'description_width': '95px'}, layout=W.Layout(width='390px', max_width='100%'))
            control.observe(self.changed, names='value'); self.controls[key] = control
        note = W.HTML('<p>FDOT SDG Table 1.4.2-1 · exterior substructure cover. Confirm each face condition; '
                      'unknown conditions stay pending in D/C checks. Sides / ends use their most severe exposure. '
                      'Active bar sizes are checked automatically against SDM 4.3.11.</p>')
        box = W.VBox([note, W.HBox(list(self.controls.values()), layout=W.Layout(flex_flow='row wrap'))])
        self.ui = W.Accordion(children=[box], selected_index=None, layout=W.Layout(width='100%'))
        self.ui.set_title(0, 'FDOT detailing · cover exposure and bar limits')
        self.widgets = [note, *box.children[1:], box]

    def changed(self, _):
        if self.busy or self.owner.busy:
            return
        self.owner.case['fdot_detailing'] = {k: w.value for k, w in self.controls.items()}
        self.owner.refresh(); self.owner._notify_case_change()

    def load(self):
        self.busy = True
        try:
            for k, w in self.controls.items():
                w.value = settings(self.owner.case)[k]
        finally:
            self.busy = False

    def close(self):
        for w in [*self.controls.values(), *self.widgets, self.ui]:
            w.close()
