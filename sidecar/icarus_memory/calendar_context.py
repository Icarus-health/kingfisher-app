"""Bounded situational context from the existing local EventKit snapshot.

No network, relationship inference, or second calendar store. Dates retain their
UTC offset; missing or stale coverage never establishes absence of meetings.
"""
from datetime import datetime, timedelta, timezone


def _timestamp(value):
    try:
        # Python 3.10 needs UTC-Z normalization for worker JSON timestamps.
        if isinstance(value, str) and value.endswith('Z'):
            value = value[:-1] + '+00:00'
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def snapshot(state, *, at=None):
    at = at or datetime.now(timezone.utc)
    end = at + timedelta(days=7)
    result = dict(status='disabled', scope='selected_mac_calendars',
                  observed_at=at.isoformat(), window_from=at.isoformat(),
                  window_to=end.isoformat(), synced_at=None, coverage='unknown',
                  events=[], truncated=False, invalid_count=0)
    if not state or not state.get('enabled') or not state.get('selected'):
        return result
    result['status'] = 'unavailable'
    if state.get('status') != 'granted' or state.get('error'):
        return result
    synced = _timestamp(state.get('synced_at'))
    result['status'] = 'stale'
    if synced:
        result['synced_at'] = synced.isoformat()
    if synced is None or not timedelta(0) <= at - synced <= timedelta(minutes=5):
        return result
    lower, upper = _timestamp(state.get('range_from')), _timestamp(state.get('range_to'))
    if lower and upper:
        result['coverage'] = 'covered' if lower <= at and upper >= end else 'partial'
    selected = set(state['selected'])
    candidates = []
    raw_events = state.get('events') or []
    result['truncated'] = len(raw_events) > 10000
    for event in raw_events[:10000]:
        start, finish = _timestamp(event.get('start')), _timestamp(event.get('end'))
        uid, source = event.get('uid'), event.get('source_id')
        if (not start or not finish or finish < start or not isinstance(uid, str)
                or not uid or len(uid) > 8192 or not isinstance(source, str)
                or len(source) > 1024):
            result['invalid_count'] += 1
            continue
        if source not in selected or finish <= at or start >= end:
            continue
        candidates.append((start, uid, source, event, finish))
    candidates.sort(key=lambda item: item[:3])
    # Overall character budget includes potentially long opaque identifiers.
    budget = 16000
    for start, uid, source, event, finish in candidates:
        item = dict(uid=uid, source_id=source, start=start.isoformat(), end=finish.isoformat(),
                    summary=str(event.get('summary', ''))[:400],
                    source_label=str(event.get('source_label', ''))[:120],
                    location=str(event.get('location', ''))[:200],
                    all_day=bool(event.get('all_day')))
        size = len(str(item))
        if len(result['events']) >= 12 or size > budget:
            result['truncated'] = True
            continue
        result['events'].append(item)
        budget -= size
    result['status'] = 'available'
    return result


def local_snapshot(calendar):
    """Read one coherent authorized snapshot; never expose raw exception text."""
    try:
        return snapshot(calendar.read() if calendar is not None else None)
    except Exception:
        result = snapshot(None)
        result['status'] = 'unavailable'
        return result


def fingerprint(context):
    """Semantic snapshot identity; routine sync timestamps do not reset chat."""
    import hashlib
    import json
    payload = {key: value for key, value in context.items()
               if key not in {'observed_at', 'synced_at', 'window_from', 'window_to'}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
