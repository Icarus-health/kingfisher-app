"""Read-only temporal eligibility, never proof that an obligation is still open."""
from datetime import datetime, timedelta, timezone
import hashlib
import re

from .episodes import sql_nicht_ignoriert
from .model import SourceType

# A selection window for unconfirmed suggestions, not an expiry for real tasks.
RECENT_WINDOW = timedelta(days=7)
SELF = 'mail:message:'
REPLY = 'mail:reply:'
REASONS = {
    'history': 'Aus dem importierten Bestand. Ob diese Bitte noch offen ist, muss geprüft werden.',
    'old': 'Historische Quelle. Der heutige Import macht daraus keine aktuelle Aufgabe.',
    'unknown': 'Quelldatum unbekannt. Der Importzeitpunkt ersetzt kein Quelldatum.',
    'future': 'Quelldatum liegt in der Zukunft. Bitte die zeitliche Einordnung prüfen.',
    'followup': 'Weitere Nachricht im selben Verlauf vorhanden. Die frühere Bitte muss im Zusammenhang geprüft werden.',
    'recent': 'Zeitnahe Quelle; weiterhin ein unbestätigter Aufgabenvorschlag.',
}


def date_status(date, *, now):
    if date is None or date.tzinfo is None:
        return 'unknown'
    if date > now:
        return 'future'
    return 'old' if date < now - RECENT_WINDOW else 'recent'


def _token(account, value):
    return hashlib.sha256((account + '\0' + value).encode()).hexdigest()


def thread_tags(message):
    """Exact header references scoped to one account; no subject/name guessing."""
    account = getattr(message, 'account_id', '')
    if not account:
        return []
    def token(value):
        return _token(account, value)
    def ids(value):
        return re.findall(r'<[^<>\s]{1,500}>', value[:16000])[:64]
    own = ids(getattr(message, 'message_id', '') or '')
    refs = ids(getattr(message, 'in_reply_to', '') or '')
    refs += ids(' '.join((getattr(message, 'references', ()) or ())[:64]))
    return ([SELF + token(own[0])] if len(own) == 1 else []) + list(dict.fromkeys(REPLY + token(ref) for ref in refs if ref not in own))


class ReplyIndex:
    """Transient, bounded header hints. Parse stored JSON at most once per request."""
    MAX_HINTS = 50000

    def __init__(self, episodes, *, wanted=None):
        self.episodes, self.wanted = episodes, wanted
        self.links = None
        self.incomplete = False

    def get(self, ref, source_id):
        if self.links is None:
            self.links = {}
            query = "SELECT e.id,j.value,julianday(e.occurred_at),julianday(e.recorded_at) FROM episodes e, json_each(e.document,'$.tags') j WHERE " + sql_nicht_ignoriert('e')
            query += " AND json_extract(e.document,'$.provenance.source_type')='email' AND j.value LIKE 'mail:reply:%'"
            params = []
            if self.wanted:
                query += ' AND j.value IN (' + ','.join('?' for _ in self.wanted) + ')'
                params = list(self.wanted)
            with self.episodes._lock:
                cursor = self.episodes._conn.execute(query, params)
                while rows := cursor.fetchmany(200):
                    for episode_id, token, occurred, recorded in rows:
                        if token not in self.links and len(self.links) >= self.MAX_HINTS:
                            self.incomplete = True
                            break
                        ids = self.links.setdefault(token, [])
                        # Prefer the newest dated source, never its import order.
                        # Retain two so a source cannot count itself as a follow-up.
                        entry = (occurred is not None, occurred or 0, recorded or 0, episode_id)
                        if not any(i[-1] == episode_id for i in ids):
                            ids.append(entry)
                            ids.sort(reverse=True)
                            del ids[2:]
                    if self.incomplete:
                        break
                cursor.close()
        return next((i[-1] for i in self.links.get(ref, []) if i[-1] != source_id), None)


def timings(episodes, sources, *, now, relations=None):
    """One bounded batch: intake lookup and shared header hints; no original text is returned."""
    now = now.astimezone(timezone.utc)
    result = {}
    ids = [e.id for e in sources]
    if not ids:
        return result
    with episodes._lock:
        history = {r[0] for r in episodes._conn.execute(
            'SELECT DISTINCT episode_id FROM mail_intake_items WHERE lane=\'history\' AND episode_id IN (' + ','.join('?' for _ in ids) + ')', ids)}
        eligible = {}
        for e in sources:
            date = e.occurred_at
            status = date_status(date, now=now)
            if e.provenance.source_type is SourceType.EMAIL and status == 'recent' and e.id in history:
                status = 'history'
            result[e.id] = {'received_at': date.astimezone(timezone.utc).isoformat() if date else None,
                'recorded_at': e.recorded_at.astimezone(timezone.utc).isoformat(), 'temporal_status': status,
                'temporal_reason': REASONS[status], 'followup_episode_id': None}
            if status == 'recent' and e.provenance.source_type is SourceType.EMAIL:
                tags = list(e.tags)
                # Older captures already retained account-scoped Message-ID provenance.
                legacy = re.fullmatch(r'(.+):(<[^<>\s]{1,500}>)', e.provenance.source_ref or '')
                if legacy:
                    tags.append(SELF + _token(*legacy.groups()))
                for tag in tags:
                    if tag.startswith(SELF):
                        eligible.setdefault(REPLY + tag[len(SELF):], set()).add(e.id)
        if eligible:
            relations = relations or ReplyIndex(episodes, wanted=eligible)
            for ref, source_ids in eligible.items():
                for source_id in source_ids:
                    other = relations.get(ref, source_id)
                    if other:
                        result[source_id].update(temporal_status='followup', temporal_reason=REASONS['followup'], followup_episode_id=other)
                    elif relations.incomplete:
                        result[source_id].update(temporal_status='context_limit', temporal_reason='Der Verlauf ist zu umfangreich für diese automatische Prüfung. Bitte ausdrücklich prüfen.')
    return result


def message_timing(episodes, message, *, now):
    """Inspect an opened mail without recording it or replacing its unknown date."""
    from types import SimpleNamespace
    from .mail_ingestion import source_key_for_message
    from .model import Provenance
    head = episodes.source_head(source_key_for_message(message))
    previous = episodes.get(head) if head else None
    source = SimpleNamespace(id=head or '', occurred_at=message.date,
        recorded_at=previous.recorded_at if previous else now,
        tags=thread_tags(message), provenance=Provenance(source_type=SourceType.EMAIL))
    result = timings(episodes, [source], now=now)[source.id]
    if previous is None:
        result['recorded_at'] = None  # viewing is not an import
    return result
