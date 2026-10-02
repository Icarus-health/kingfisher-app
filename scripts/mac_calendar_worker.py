#!/usr/bin/env python3
"""Outbound-only local worker. No tokens on command lines, no event logging."""
import argparse
import fcntl
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    parser.add_argument('--env-file', required=True, type=Path)
    args = parser.parse_args()
    url = urlparse(args.url)
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username or url.path not in ('', '/'):
        parser.error('Only an explicit 127.0.0.1 HTTP service is supported')
    lock = args.env_file.with_suffix('.calendar.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    config = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines()
                  if '=' in line and not line.startswith('#'))
    token = config.get('ICARUS_SIDECAR_TOKEN')
    if not token:
        parser.error('ICARUS_SIDECAR_TOKEN missing from private env file')
    binary = Path(__file__).resolve().parents[1] / 'build/kingfisher-calendar'
    opener = build_opener(ProxyHandler({}), NoRedirect())

    def api(body=None, route='/worker'):
        data = None if body is None else json.dumps(body).encode()
        request = Request(args.url.rstrip('/') + '/api/v1/mac-calendar' + (route if body is not None else ''),
                          data=data, headers={'X-Icarus-Token': token, 'Content-Type': 'application/json'})
        with opener.open(request, timeout=60) as response:
            return json.load(response)

    def reader(command, payload=None):
        result = subprocess.run([str(binary), command], input=json.dumps(payload or {}),
                                text=True, capture_output=True, timeout=130 if command == 'authorize' else 30)
        return json.loads(result.stdout)

    def sync_memory(state):
        """Liest das Gedächtnisfenster (Zeitraum kommt vom Sidecar) abschnittsweise, mit Notizen.

        Jeder Abschnitt (90 Tage) geht vollständig an den Sidecar, der ihn mit dem
        Gedächtnis abgleicht. Die Live-Anzeige bleibt davon unberührt.
        """
        window = state.get('memory_window') or {}
        today = datetime.now(timezone.utc)
        first = today - timedelta(days=window.get('days_back', 3 * 365))
        last = today + timedelta(days=window.get('days_ahead', 365))
        cursor = first
        while cursor < last:
            section_end = min(cursor + timedelta(days=90), last)
            events = {}
            step = cursor
            while step < section_end:
                stop = min(step + timedelta(days=31), section_end)
                snapshot = reader('events', {'calendar_ids': state['selected'], 'start': step.isoformat(),
                                             'end': stop.isoformat(), 'with_notes': True})
                if not snapshot.get('ok'):
                    raise RuntimeError('calendar memory read failed')
                for event in snapshot['events']:
                    events[event['uid']] = event
                step = stop
            api({'generation': state['generation'], 'range_from': cursor.isoformat(),
                 'range_to': section_end.isoformat(), 'events': sorted(events.values(), key=lambda e: e['start'])},
                route='/memory')
            cursor = section_end

    last_sync = 0
    last_memory = 0
    memory_generation = -1
    generation = -1
    while True:
        try:
            state = api()
            result = reader('status')
            if state['enabled'] and state['authorize'] and result.get('status') != 'granted':
                result = reader('authorize')
            update = {'generation': state['generation'], 'status': result.get('status', 'error')}
            if state['enabled'] and update['status'] == 'granted':
                listing = reader('calendars')
                if not listing.get('ok'):
                    raise RuntimeError('calendar listing failed')
                update['calendars'] = listing['calendars']
                if state['selected'] and (not state['synced_at'] or generation != state['generation'] or time.monotonic() - last_sync > 60):
                    year = datetime.now().year
                    start = datetime(year, 1, 1, tzinfo=timezone.utc) - timedelta(days=2)
                    finish = datetime(year + 1, 1, 1, tzinfo=timezone.utc) + timedelta(days=2)
                    cursor = start
                    events = {}
                    while cursor < finish:
                        stop = min(cursor + timedelta(days=31), finish)
                        snapshot = reader('events', {'calendar_ids': state['selected'],
                            'start': cursor.isoformat(), 'end': stop.isoformat()})
                        if not snapshot.get('ok'):
                            raise RuntimeError('calendar read failed')
                        for event in snapshot['events']:
                            events[event['uid']] = event
                        if len(events) > 10000:
                            raise RuntimeError('calendar event limit exceeded')
                        cursor = stop
                    update['events'] = sorted(events.values(), key=lambda e: e['start'])
                    update['range_from'] = start.isoformat()
                    update['range_to'] = finish.isoformat()
                    last_sync = time.monotonic()
                    generation = state['generation']
            api(update)
            if (state['enabled'] and update['status'] == 'granted' and state['selected']
                    and (memory_generation != state['generation'] or time.monotonic() - last_memory > 1800)):
                try:
                    sync_memory(state)
                    memory_generation = state['generation']
                    last_memory = time.monotonic()
                except (HTTPError, OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                    # Ein Fehler im Gedächtnisabgleich darf die Live-Anzeige nicht als defekt melden.
                    last_memory = time.monotonic() - 1500  # in fünf Minuten erneut versuchen
                    print('Mac calendar memory sync failed; retrying.', flush=True)
        except HTTPError as error:
            print('Mac calendar connection:', error.code, flush=True)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            print('Mac calendar temporarily unavailable; retrying.', flush=True)
            try:
                api({'generation': state['generation'], 'status': 'error',
                     'error': 'Mac-Kalender konnte nicht gelesen werden. Bitte Freigabe und Auswahl prüfen.'})
            except Exception:
                pass
        time.sleep(5)


if __name__ == '__main__':
    main()
