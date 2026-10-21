"""Recorded closures and overrides for individual checks (the backwall pattern, shared by the journal calculations).

A review stores a fingerprint of the calculated result it was made against. If inputs change the calculated status,
ratio, demand or capacity, the review is retained but marked as needing review and the calculated status is shown again.
"""
from datetime import datetime, timezone
import hashlib
import html
import json

ACTIONS = {'close': 'PASS · CLOSED', 'override': 'PASS · OVERRIDE'}


def fingerprint(check):
    status = getattr(check, 'calc_status', None) or check.status
    ratio = None if check.ratio is None else round(float(check.ratio), 6)
    basis = json.dumps([check.key, status, ratio, check.demand, check.capacity])
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]


def apply_reviews(e):
    reviews = e.case.get('reviews', {})
    for check in e.checks:
        check.calc_status = check.status
        record = reviews.get(check.key)
        if not record:
            continue
        check.review = dict(record)
        if record.get('fingerprint') != fingerprint(check):
            check.review['stale'] = True
            check.note = (check.note + ' ' if check.note else '') + 'Recorded review needs review: the calculated result changed.'
        else:
            check.status = ACTIONS[record['action']]


def record_review(case, check, action, reason, reviewed_by=''):
    if action not in ACTIONS:
        raise ValueError('Choose close or override.')
    if not reason.strip():
        raise ValueError('Enter a reason before recording the review.')
    calculated = getattr(check, 'calc_status', None) or check.status
    if action == 'close' and 'FAIL' in calculated:
        raise ValueError('A failed check can only be recorded as an override.')
    previous = case.setdefault('reviews', {}).get(check.key, {})
    entry = dict(action=action, reason=reason.strip(), reviewed_by=reviewed_by.strip(),
                 utc=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                 original_status=calculated, ratio=check.ratio)
    case['reviews'][check.key] = dict(entry, fingerprint=fingerprint(check), history=previous.get('history', []) + [entry])
    return case


def reopen(case, key):
    record = case.get('reviews', {}).pop(key, None)
    if record:
        case.setdefault('review_history', {}).setdefault(key, []).extend(record.get('history', []))
    return case


def review_html(check):
    r = check.review
    if not r:
        return ''
    stale = '<b style="color:#9d302b">Needs review</b> · ' if r.get('stale') else ''
    who = (' · ' + html.escape(r['reviewed_by'])) if r.get('reviewed_by') else ''
    return (f'<div class="ebw-review">{stale}<b>{html.escape(ACTIONS[r["action"]])}</b> · calculated '
            f'{html.escape(str(r.get("original_status", "")))} · {html.escape(r["utc"])}{who}<br>{html.escape(r["reason"])}</div>')
