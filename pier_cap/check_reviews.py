"""Recorded check dispositions, separate from calculated resistance and search gates."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import math


ACTIONS = {'close_pending': 'Closed as passed', 'override': 'Override as passed', 'reopen': 'Reopened'}


def is_pending(status):
    return any(word in status for word in ('PENDING', 'CONDITIONAL', 'PROVISIONAL')) and 'FAIL' not in status


def _digest(value):
    # JSON loads and widget edits may interchange integer and float operands.
    def normalized(item):
        if type(item) in (int, float):return format(item, '.12g')
        if isinstance(item, dict):return {k: normalized(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):return [normalized(v) for v in item]
        return item
    return sha256(json.dumps(normalized(value), sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def case_fingerprint(case):
    return _digest({k: v for k, v in case.items() if k not in ('check_reviews', 'name', 'description')})


def original_status(check):
    return getattr(check, 'calculated_status', '') or check.status


def original_basis(check):
    return getattr(check, 'calculated_basis', '') or check.basis


def check_fingerprint(check):
    return _digest([check.key, check.label, original_status(check), check.ratio, original_basis(check)])


def validate_reviews(case):
    if 'check_reviews' not in case:return
    data = case['check_reviews']
    if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1 or not isinstance(data.get('records'), list):
        raise ValueError('Invalid check review history or version.')
    for record in data['records']:
        if not isinstance(record, dict) or not isinstance(record.get('action'), str) or record['action'] not in ACTIONS:
            raise ValueError('Invalid check review action.')
        for key in ('check_key', 'check_label', 'reason', 'recorded_at', 'original_status', 'original_basis', 'case_fingerprint', 'check_fingerprint'):
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError('Check review requires nonblank '+key+'.')
        if record['check_key'] == 'Status_overall':raise ValueError('Review individual checks; the overall summary is automatic.')
        if not isinstance(record.get('reviewed_by', ''), str):raise ValueError('Check reviewer must be text.')
        ratio = record.get('original_ratio')
        if not isinstance(ratio, str) and (type(ratio) not in (int, float) or not math.isfinite(ratio)):
            raise ValueError('Invalid original check ratio.')
        for key in ('case_fingerprint', 'check_fingerprint'):
            if len(record[key]) != 64 or any(c not in '0123456789abcdef' for c in record[key]):
                raise ValueError('Invalid check review fingerprint.')
        try:
            stamp = datetime.fromisoformat(record['recorded_at'])
            if stamp.utcoffset() is None:raise ValueError()
        except ValueError as exc:raise ValueError('Check review timestamp must include its time zone.') from exc


def review_history(e):
    records = getattr(e, 'case', {}).get('check_reviews', {}).get('records', [])
    if not records:return []
    last = {r['check_key']: i for i, r in enumerate(records)}
    checks = {c.key: c for c in e.checks}
    fingerprint = case_fingerprint(e.case)
    rows = []
    for i, record in enumerate(records):
        check = checks.get(record['check_key'])
        if last[record['check_key']] != i:state = 'Superseded'
        elif record['action'] == 'reopen':state = 'Reopened'
        elif check is None:state = 'Check unavailable'
        elif record['case_fingerprint'] != fingerprint or record['check_fingerprint'] != check_fingerprint(check):state = 'Needs review'
        else:state = 'Active'
        rows.append(dict(record, state=state))
    return rows


def retain_reviews(source, target):
    """Keep audit notes when applying a candidate created before a review was saved."""
    source_records = source.get('check_reviews', {}).get('records', [])
    if not source_records:return target
    records = target.setdefault('check_reviews', dict(version=1, records=[]))['records']
    for record in source_records:
        if record not in records:records.append(deepcopy(record))
    return target


def record_review(e, key, action, reason, reviewed_by=''):
    """Return a new case; the caller reevaluates it before replacing live state."""
    if action not in ACTIONS:raise ValueError('Select a supported review action.')
    if not isinstance(reason, str) or not reason.strip():raise ValueError('Enter a reason / closure note before saving.')
    if not isinstance(reviewed_by, str):raise ValueError('Reviewer must be text.')
    check = next((c for c in e.checks if c.key == key), None)
    previous = next((r for r in reversed(review_history(e)) if r['check_key'] == key), None)
    if key == 'Status_overall':raise ValueError('Close or override individual checks; the summary updates automatically.')
    if action == 'reopen':
        if not previous or previous['action'] == 'reopen':raise ValueError('This check has no saved review to remove.')
    elif check is None or original_status(check) in ('REFERENCE', 'NOT REQUIRED'):
        raise ValueError('Select an applicable check from the current calculation.')
    if action == 'close_pending' and (not is_pending(original_status(check)) or
            isinstance(check.ratio, (int, float)) and check.ratio > 1 + 1e-8):
        raise ValueError('Close as passed is for pending checks. Use Override as passed for a failed check.')
    record = dict(check_key=key, check_label=check.label if check else previous['check_label'],
        action=action, reason=reason.strip(), reviewed_by=reviewed_by.strip(),
        recorded_at=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
        original_status=original_status(check) if check else previous['original_status'],
        original_ratio=check.ratio if check else previous['original_ratio'],
        original_basis=original_basis(check) if check else previous['original_basis'],
        case_fingerprint=case_fingerprint(e.case),
        check_fingerprint=check_fingerprint(check) if check else previous['check_fingerprint'])
    case = deepcopy(e.case)
    case.setdefault('check_reviews', dict(version=1, records=[]))['records'].append(record)
    validate_reviews(case)
    return case


def apply_reviews(e):
    """Apply only to display/register statuses after all calculation gates are evaluated."""
    for check in e.checks:
        check.calculated_status = check.status
        check.calculated_basis = check.basis
    latest = {r['check_key']: r for r in review_history(e)}
    active = 0
    for check in e.checks:
        record = latest.get(check.key)
        if not record:continue
        check.review = deepcopy(record)
        check.review_state = record['state']
        if record['state'] == 'Active':
            active += 1
            check.status = 'PASS · CLOSED' if record['action'] == 'close_pending' else 'PASS · OVERRIDE'
        note = (f"{ACTIONS[record['action']]} — {record['state']}. Original result: {record['original_status']}; "
                f"original D/C: {record['original_ratio']}. Reason: {record['reason']}\n"
                f"Recorded: {record['recorded_at']}"+(f"; reviewer: {record['reviewed_by']}" if record['reviewed_by'] else ''))
        check.basis = note+'\n\nCalculated basis: '+check.calculated_basis
    if not active:return
    summary = next((c for c in e.checks if c.key == 'Status_overall'), None)
    others = [c for c in e.checks if c.key != 'Status_overall']
    failed = any('FAIL' in c.status for c in others)
    pending = any(is_pending(c.status) for c in others)
    # The uniform summary also carries a pile-head gate not represented by a row.
    pending = pending or not e.case['inputs']['Ready_pile']
    status = 'FAIL' if failed else 'PENDING' if pending else 'PASS'
    if summary:
        summary.status = status+' · WITH RECORDED REVIEWS'
        summary.basis = (f'{active} checks accepted by recorded closure / override. '
                         'Collects current register statuses; original calculations remain available.\n'+summary.calculated_basis)
    e.status = ('CHECK REGISTER '+status+f' · {active} recorded closure(s) / override(s)'
        + (' · REIMPORT FORCES: '+', '.join(e.stale) if e.stale else '')
        + (' · DETAILING FINDINGS REMAIN' if e.issues else ''))


def history_html(e):
    records = review_history(e)
    if not records:return ''
    rows = []
    for r in reversed(records):
        cells = [r['check_label'], ACTIONS[r['action']], r['state'], r['original_status'],
                 str(r['original_ratio']), r['reason'], r.get('reviewed_by') or 'Not entered', r['recorded_at']]
        rows.append('<tr>'+''.join('<td>'+escape(v).replace('\n', '<br>')+'</td>' for v in cells)+'</tr>')
    return ('<details class="check-review-history"><summary>Check closure / override history ('+str(len(records))+')</summary>'
        '<p>PASS · CLOSED and PASS · OVERRIDE are recorded review decisions. Original ratios and calculation working are retained. '
        'Changed inputs or results require a new review. Reopening retains previous notes.</p>'
        '<table class="cap-table"><caption>Check closure and override history</caption><thead><tr>'
        +''.join('<th>'+s+'</th>' for s in ('Check', 'Action', 'State', 'Original result', 'Original D/C', 'Reason / closure note', 'Reviewer', 'Recorded (UTC)'))
        +'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></details>')


def review_note_html(check):
    record = getattr(check, 'review', None)
    if not record:return ''
    return ('<p style="white-space:pre-wrap;overflow-wrap:anywhere"><b>'+escape(ACTIONS[record['action']])+' · '+escape(record['state'])
        +'</b><br>'+escape(record['reason'])+'<br><small>Original: '+escape(record['original_status'])
        +' · D/C '+escape(str(record['original_ratio']))+'<br>'+escape(record['recorded_at'])
        +( ' · '+escape(record['reviewed_by']) if record['reviewed_by'] else '')+'</small></p>')
