"""Selected Google calendars, strictly read-only with server-expanded recurrences."""
from datetime import datetime, time, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .connectors.calendar import CalendarError, Event
from .google_oauth import CALENDAR_URL, GoogleError, google_request


class GoogleCalendar:
    def __init__(self, calendar_id, access_token, request=google_request):
        self.calendar_id, self.access_token, self.request = calendar_id, access_token, request

    def events(self, days=7, at=None):
        at = at or datetime.now(timezone.utc)
        try:
            token = self.access_token()
            page, events = None, []
            for _ in range(20):
                result = self.request('GET', CALENDAR_URL + '/calendars/' + quote(self.calendar_id, safe='') + '/events',
                    headers={'Authorization': 'Bearer ' + token}, params={
                        'timeMin': at.isoformat(), 'timeMax': (at + timedelta(days=days)).isoformat(),
                        'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': 250,
                        **({'pageToken': page} if page else {})})
                zone = ZoneInfo(result.get('timeZone', 'UTC'))
                for entry in result.get('items', []):
                    if entry.get('status') == 'cancelled':
                        continue
                    start, end = entry.get('start', {}), entry.get('end', {})
                    def parse(value):
                        if value.get('dateTime'):
                            stamp = datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
                            return stamp if stamp.tzinfo else stamp.replace(tzinfo=ZoneInfo(value.get('timeZone', str(zone))))
                        if value.get('date'):
                            return datetime.combine(datetime.fromisoformat(value['date']).date(), time.min, zone)
                        return None
                    events.append(Event(uid=entry['id'], summary=entry.get('summary', '(ohne Titel)'),
                        start=parse(start), end=parse(end), all_day='date' in start,
                        location=entry.get('location', ''),
                        attendees=[(f"{a['displayName']} <{a['email']}>" if a.get('displayName') and a['displayName'] != a['email']
                                    else a['email']) for a in entry.get('attendees', []) if a.get('email')],
                        notes=entry.get('description', '')))
                page = result.get('nextPageToken')
                if not page:
                    return events
            raise CalendarError('Google-Kalender ist zu groß für diesen Zeitraum. Bitte einen kürzeren Zeitraum wählen.')
        except (GoogleError, KeyError, ValueError, ZoneInfoNotFoundError):
            raise CalendarError('Google-Kalender nicht verfügbar. Bitte Anmeldung und Kalenderfreigabe prüfen.') from None
