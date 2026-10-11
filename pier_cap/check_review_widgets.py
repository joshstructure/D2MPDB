"""Close, override and reopen individual entries in the D/C register."""
from html import escape
import ipywidgets as W
from .check_reviews import case_fingerprint, is_pending, original_status, record_review, review_history, review_note_html


class CheckReviewPanel:
    def __init__(self, owner):
        self.owner = owner
        self.evaluation = None
        self.updating = False
        self.check = W.Dropdown(options=[], description='Check', layout=W.Layout(width='100%'),
            style={'description_width': '60px'})
        self.reason = W.Textarea(description='Reason', placeholder='Explain the closure or override and cite the checked detail / calculation.',
            layout=W.Layout(width='100%', height='90px'), style={'description_width': '60px'})
        self.reviewer = W.Text(description='Reviewer', placeholder='Name / initials (optional)',
            layout=W.Layout(width='340px'), style={'description_width': '60px'})
        self.close_pending = W.Button(description='Close as passed', icon='check', button_style='success', layout=W.Layout(width='160px'))
        self.override = W.Button(description='Override as passed', icon='edit', button_style='warning', layout=W.Layout(width='175px'))
        self.reopen = W.Button(description='Reopen check', icon='undo', layout=W.Layout(width='150px'))
        self.detail = W.HTML()
        self.message = W.HTML()
        self.ui = W.VBox([W.HTML('<h4>Close or override a check</h4><p>Select a check and enter a required reason. '
            '<b>Close as passed</b> records completion of a pending review; <b>Override as passed</b> records an exception. '
            'Original results and D/C values remain visible. Save the case or notebook JSON to keep the record between sessions.</p>'),
            self.check, self.detail, self.reason, self.reviewer,
            W.HBox([self.close_pending, self.override, self.reopen], layout=W.Layout(flex_flow='row wrap')),
            self.message], layout=W.Layout(width='100%', padding='10px', border='1px solid #dce5ec'))
        self.check.observe(self._selected, names='value')
        self.reason.observe(self._buttons, names='value')
        self.close_pending.on_click(lambda _: self._save('close_pending'))
        self.override.on_click(lambda _: self._save('override'))
        self.reopen.on_click(lambda _: self._save('reopen'))
        self.set_available(False)

    def set_available(self, available):
        self.available = available
        self.check.disabled = not available
        self.reason.disabled = not available
        self.reviewer.disabled = not available
        self._buttons()
        if not available:self.detail.value = '<p>Click <b>Recalc</b> to review the current checks.</p>'

    def refresh(self, evaluation):
        self.evaluation = evaluation
        checks = [c for c in evaluation.checks if c.key != 'Status_overall' and original_status(c) not in ('REFERENCE', 'NOT REQUIRED')]
        checks.sort(key=lambda c: (0 if is_pending(c.status) else 1 if 'FAIL' in c.status else 2))
        options = [(c.label+' — '+c.status, c.key) for c in checks]
        keys = {key for _, key in options}
        latest = {r['check_key']: r for r in review_history(evaluation)}
        for key, record in latest.items():
            if key not in keys and record['action'] != 'reopen':
                options.append((record['check_label']+' — '+record['state'], key))
        selected = self.check.value
        self.updating = True
        try:
            self.check.options = options
            self.check.value = selected if selected in {key for _, key in options} else options[0][1] if options else None
        finally:self.updating = False
        self.set_available(True)
        self._selected()

    def _selected(self, change=None):
        if self.updating:return
        self.reason.value = ''
        self.message.value = ''
        current = next((c for c in self.evaluation.checks if c.key == self.check.value), None) if self.evaluation else None
        if current:
            self.detail.value = ('<p><b>Calculated result:</b> '+escape(original_status(current))+' · D/C '+escape(str(current.ratio))
                +'</p>'+review_note_html(current))
            if current.review and current.review['action'] != 'reopen':self.reason.value = current.review['reason']
        else:self.detail.value = '<p>This saved check is unavailable in the current calculation. Its history can be reopened.</p>'
        self._buttons()

    def _buttons(self, change=None):
        e = self.evaluation
        current = next((c for c in e.checks if c.key == self.check.value), None) if e else None
        ready = getattr(self, 'available', False) and not self.owner.dirty and not self.owner.calculating
        noted = bool(self.reason.value.strip())
        self.override.disabled = not (ready and noted and current and original_status(current) not in ('REFERENCE', 'NOT REQUIRED'))
        self.close_pending.disabled = self.override.disabled or not is_pending(original_status(current)) or (
            isinstance(current.ratio, (int, float)) and current.ratio > 1 + 1e-8)
        previous = next((r for r in reversed(e.case.get('check_reviews', {}).get('records', [])) if r['check_key'] == self.check.value), None) if e else None
        self.reopen.disabled = not (ready and previous and previous['action'] != 'reopen')

    def _save(self, action):
        owner = self.owner
        try:
            if owner.dirty or owner.calculating or self.evaluation is None or case_fingerprint(owner.case) != case_fingerprint(self.evaluation.case):
                raise ValueError('Click Recalc before recording a check review.')
            reason = self.reason.value if action != 'reopen' else 'Review removed; return to calculated result.'
            candidate = record_review(self.evaluation, self.check.value, action, reason, self.reviewer.value)
            from .model import evaluate
            from .visuals import side_steel_html
            evaluated = evaluate(candidate)
            side = side_steel_html(evaluated)
            owner.case = candidate
            owner._calculation_ready(evaluated, side)
            owner._notify_case_change()
            self.message.value = '<p><b>Review recorded.</b> Save case JSON or Save both sections to keep it. JSON and report exports include the history.</p>'
        except Exception as exc:
            self.message.value = '<p role="alert" style="color:#9d302b">'+escape(str(exc))+'</p>'

    def close(self):
        for widget in (self.check, self.reason, self.reviewer, self.close_pending, self.override, self.reopen, self.detail, self.message, self.ui):widget.close()
