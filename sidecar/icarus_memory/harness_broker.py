"""Read-only, short-lived capabilities; no worker receives a store or master key.

This is an authorization boundary, not process isolation. Production wiring is
deliberately separate from the standalone artificial-data experiment.
"""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import secrets
import threading
import time

from .episodes import AUSGEBLENDETE_ZUSTAENDE, CHAT_LOOKUP_TAG
from .memory_source_search import literal_span, excerpt_bounds


class BridgeError(ValueError):
    """No underlying provider exception, source text or secret in public errors."""


@dataclass
class _Grant:
    id: str
    request: str
    area: str
    expires: float
    sources: dict
    selection: dict
    discovered: set = field(default_factory=set)
    tool_calls: int = 0
    model_calls: int = 0
    requests: int = 0
    active: bool = True


class Broker:
    def __init__(self, episodes, procedures, *, clock=time.monotonic, max_grants=16):
        self.episodes, self.procedures = episodes, procedures
        self._clock, self._max = clock, max_grants
        self._grants = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(token):
        if not isinstance(token, str) or not 32 <= len(token) <= 128:
            raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
        return hashlib.sha256(token.encode()).hexdigest()

    def _snapshot(self, identifier):
        try:
            snap = self.episodes.support_snapshot(identifier)
        except (ValueError, KeyError):
            snap = None
        if (not snap or not snap.current() or snap.episode.state in AUSGEBLENDETE_ZUSTAENDE
                or CHAT_LOOKUP_TAG in snap.episode.tags):
            raise BridgeError('Eine Grundlage ist nicht mehr verfügbar.')
        return snap

    def issue(self, request, *, area, sources, ttl=120):
        """Trusted controller only. Never exposed as a worker capability."""
        if (not isinstance(request, str) or not 1 <= len(request.strip()) <= 1200
                or area not in {'mail', 'planning', 'analysis'}
                or type(ttl) not in (int, float) or not 0 < ttl <= 120
                or not isinstance(sources, list) or not 1 <= len(sources) <= 20
                or any(not isinstance(s, str) or not 1 <= len(s) <= 80 for s in sources)
                or len(set(sources)) != len(sources)):
            raise BridgeError('Der Leseauftrag ist nicht ausreichend eingegrenzt.')
        with self._lock:
            self._grants = {k:g for k,g in self._grants.items()
                            if g.active and self._clock() < g.expires}
            if len(self._grants) >= self._max:
                raise BridgeError('Zu viele gleichzeitige Arbeitsläufe.')
            stamps = {s:self._snapshot(s).support_fingerprint() for s in sources}
            selected = self.procedures.select(request, area=area, local=True)
            token = secrets.token_urlsafe(32)
            grant = _Grant(secrets.token_hex(16), request, area, self._clock()+ttl,
                           stamps, deepcopy(selected))
            self._grants[self._key(token)] = grant
            self._fresh(grant)
            return dict(id=grant.id, token=token, ttl=ttl)

    def _fresh(self, grant):
        if not grant.active or self._clock() >= grant.expires:
            raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
        try:
            if any(self._snapshot(s).support_fingerprint() != stamp
                   for s,stamp in grant.sources.items()):
                raise BridgeError('Eine Grundlage hat sich geändert.')
            selected = self.procedures.select(grant.request, area=grant.area, local=True)
            if (not self.procedures.current(grant.selection)
                    or selected['signature'] != grant.selection['signature']
                    or selected['conflicts'] != grant.selection['conflicts']):
                raise BridgeError('Die passenden Arbeitsverfahren haben sich geändert.')
        except BridgeError:
            grant.active = False
            raise

    def _grant(self, token):
        grant = self._grants.get(self._key(token))
        if grant is None:
            raise BridgeError('Arbeitszugriff ungültig oder abgelaufen.')
        self._fresh(grant)
        return grant

    def authorize_request(self, token):
        with self._lock:
            grant = self._grant(token)
            if grant.requests >= 40:
                raise BridgeError('Die Anfragegrenze dieses Arbeitslaufs ist erreicht.')
            grant.requests += 1

    def cancel(self, identifier):
        with self._lock:
            for grant in self._grants.values():
                if secrets.compare_digest(grant.id, identifier):
                    grant.active = False

    @staticmethod
    def _exact(args, fields):
        if not isinstance(args, dict) or set(args) != set(fields):
            raise BridgeError('Ungültige Werkzeugargumente.')

    @staticmethod
    def _excerpt(snap, start, end):
        episode = snap.episode
        return dict(id=episode.id, title=episode.title, quote=episode.body[start:end],
            start=start, end=end, fingerprint=snap.support_fingerprint(),
            occurred_at=episode.occurred_at.isoformat() if episode.occurred_at else None,
            recorded_at=episode.recorded_at.isoformat(),
            source_type=episode.provenance.source_type.value, status='source_reports_unconfirmed')

    def invoke(self, token, name, args):
        with self._lock:
            grant = self._grant(token)
            if grant.tool_calls >= 8:
                raise BridgeError('Die Werkzeuggrenze dieses Arbeitslaufs ist erreicht.')
            grant.tool_calls += 1
            if name == 'memory_search':
                self._exact(args, {'query'})
                query = args['query']
                if (not isinstance(query, str) or not 2 <= len(query.strip()) <= len(query) <= 200
                        or any(ord(c) < 32 for c in query)):
                    raise BridgeError('Bitte einen wörtlichen Suchbegriff mit 2 bis 200 Zeichen verwenden.')
                folded = query.strip().casefold()
                items = []
                for identifier in grant.sources:
                    snap = self._snapshot(identifier)
                    span = literal_span(snap.episode.body, folded)
                    if span is not None or folded in snap.episode.title.casefold():
                        start, end = excerpt_bounds(snap.episode.body, span)
                        items.append(self._excerpt(snap, start, end))
                        grant.discovered.add(identifier)
                result = dict(items=items, scope='selected_originals_literal',
                              scanned=len(grant.sources), truncated=False)
            elif name == 'source_excerpt':
                self._exact(args, {'id', 'start', 'end'})
                identifier, start, end = args['id'], args['start'], args['end']
                if (not isinstance(identifier, str) or identifier not in grant.discovered
                        or type(start) is not int or type(end) is not int
                        or not 0 <= start < end <= start+400):
                    raise BridgeError('Nur entdeckte Originalausschnitte dürfen geöffnet werden.')
                snap = self._snapshot(identifier)
                if end > len(snap.episode.body):
                    raise BridgeError('Der Ausschnitt liegt außerhalb des Originaltexts.')
                result = self._excerpt(snap, start, end)
            elif name == 'skills_select':
                self._exact(args, set())
                result = deepcopy(grant.selection)
            else:
                raise BridgeError('Dieses Werkzeug ist nicht freigegeben.')
            self._fresh(grant)
            return result

    def model(self, token, infer):
        """Charge before transport; cancellation is possible while the model runs."""
        with self._lock:
            grant = self._grant(token)
            if grant.model_calls >= 3:
                raise BridgeError('Die Modellgrenze dieses Arbeitslaufs ist erreicht.')
            grant.model_calls += 1
        result = infer()
        with self._lock:
            self._fresh(grant)
        return result
