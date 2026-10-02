"""Explizite lokale Belegprüfung, getrennt von sachlicher Bestätigung."""
from datetime import timedelta
import json
from sqlite3 import Error as SqliteError
from .proposals import ProposalError
from secrets import token_urlsafe
from threading import RLock
from .model import Sensitivity, Status, now
from .currency import evidence_date, judge
from .self_model_basis import FrozenBuild, digest, eligible, _RANK
from .self_model_support import EpisodeSupportResolver, authorization, corresponds


class SupportReviewConflict(ValueError):
    pass


class SupportReview:
    def __init__(self, store, proposals, episodes, audit=None, *, clock=now):
        self.store, self.proposals, self.episodes, self.audit = store, proposals, episodes, audit
        self.resolver = EpisodeSupportResolver(proposals, episodes)
        self.clock = clock
        self.tokens = {}
        self.lock = RLock()
        # Authentifizierte lokale Anzeige; keine Providerfreigabe.
        self.ceiling = Sensitivity.SPECIAL_CATEGORY

    def _purge(self, at):
        self.tokens = {key: value for key, value in self.tokens.items() if value['expires'] > at}

    def _inspect(self, identifier, at):
        root = self.store.get(identifier)
        if root is None or root.status is Status.REDACTED or _RANK[root.sensitivity] > _RANK[self.ceiling]:
            return None
        build = self.resolver.build(at=at, local=True, max_sensitivity=self.ceiling, prospective=identifier)
        support_state = self.resolver.build(at=at, local=True, max_sensitivity=self.ceiling).assess(root)
        item = {'id': root.id, 'statement': root.statement, 'kind': root.kind.value,
                'factual_at': evidence_date(root).isoformat(), 'currency': judge(root, at).value,
                'support_status': 'supported' if support_state.usable else 'review_required' if support_state.complete_private else 'unavailable',
                'eligible': False, 'reason': 'Die vollständigen Originalbelege sind nicht verfügbar.'}
        try:
            producers, _ = build.producer(root)
        except (ValueError, TypeError, KeyError, AttributeError, SqliteError, ProposalError):
            return {'item': item}
        if root.status is not Status.ACTIVE or not eligible(root, at):
            item['reason'] = 'Diese Aussage ist nicht mehr aktiv oder liegt außerhalb ihres Gültigkeitszeitraums.'
            return {'item': item}
        if len(producers) != 1 or not corresponds(producers[0], root):
            return {'item': item}
        proposal = producers[0]
        if _RANK[proposal.sensitivity] > _RANK[self.ceiling]:
            return None
        try:
            support = build.capture(proposal)
            frozen = FrozenBuild(self.store, at=at, max_sensitivity=self.ceiling, support_build=build)
            ancestry = frozen.assess(root)
            if ancestry is None:
                return {'item': item}
            # Eine historisch qualifizierte Abstammung ist keine neue Belegfreigabe.
            if any(not build.assess(node).usable for key, node in frozen.nodes.items() if key != root.id):
                return {'item': item}
        except (ValueError, TypeError, KeyError, AttributeError):
            return {'item': item}
        item.update(eligible=True, reason=None)
        binding = {'root': digest(root.to_dict()), 'producer': digest(proposal.to_dict()),
                   'commitment': self.proposals.support_authorization(proposal.id),
                   'sources': [build.sources[e['episode_id']].fingerprint() for e in support['episodes']],
                   'ancestry': ancestry.signature, 'scope': self.ceiling.value, 'support': support}
        if len(json.dumps(binding, ensure_ascii=False).encode('utf-8')) > 524288:
            item.update(eligible=False, reason='Die Belege sind für eine gemeinsame Prüfung zu umfangreich.')
            return {'item': item}
        return {'item': item, 'binding': digest(binding), 'root': root, 'proposal': proposal,
                'support': support, 'expected': binding['root'],
                'evidence': [{'episode_id': e['episode_id'], 'quote': e['quote'],
                    'title': build.sources[e['episode_id']].episode.title} for e in support['episodes']]}

    def preview(self, identifier):
        with self.lock:
            at = self.clock()
            self._purge(at)
            inspected = self._inspect(identifier, at)
            if inspected is None:
                raise SupportReviewConflict('Diese Aussage ist nicht verfügbar.')
            result = {'item': inspected['item'], 'evidence': [], 'preview_token': None, 'expires_at': None}
            if not inspected['item']['eligible']:
                return result
            while len(self.tokens) >= 256:
                self.tokens.pop(next(iter(self.tokens)))
            token, expires = token_urlsafe(32), at + timedelta(minutes=10)
            self.tokens[token] = {'id': identifier, 'binding': inspected['binding'], 'expires': expires}
            result.update(evidence=inspected['evidence'], preview_token=token, expires_at=expires.isoformat())
            return result

    def submit(self, identifier, token, confirmed):
        with self.lock:
            at = self.clock()
            self._purge(at)
            ticket = self.tokens.pop(token, None)
            if confirmed is not True or ticket is None or ticket['id'] != identifier:
                raise SupportReviewConflict('Die Vorschau ist abgelaufen oder wurde bereits verwendet. Bitte neu laden.')
            # Einheitliche Reihenfolge mit der Annahme; Commitments sind die dauerhafte
            # Autorisierungsentscheidung. Ein zusätzlicher Auditfehler ist eine Warnung.
            with self.proposals.transaction():
                inspected = self._inspect(identifier, at)
                if inspected is None or not inspected['item']['eligible'] or inspected['binding'] != ticket['binding']:
                    raise SupportReviewConflict('Die Aussage oder ihre Belege haben sich geändert. Bitte neu laden.')
                old = inspected['root'].episode_support
                root = self.store.reassess_support(identifier, inspected['expected'], inspected['support'], at=at)
                commitment = authorization(root, inspected['support'], 'reassessment', at)
                self.proposals._issue_support_authorization(inspected['proposal'].id, commitment)
                assessment = self.resolver.build(at=at, local=True, max_sensitivity=self.ceiling).assess(root)
                if not assessment.complete_private or not assessment.usable:
                    raise SupportReviewConflict('Die Belege haben sich während der Prüfung geändert.')
            warning = None
            if self.audit:
                try:
                    self.audit.record('self_model.support_reassessment', 'local', 'explicit', 'executed',
                        {'assertion_id': identifier, 'proposal_id': inspected['proposal'].id,
                         'authorization_id': commitment['authorization_id'], 'old_support_hash': digest(old),
                         'new_support_hash': commitment['support_hash'], 'authorized_at': commitment['authorized_at']},
                        approved_by='user', at=at)
                except Exception:
                    warning = 'Belegnutzung erneut geprüft; der zusätzliche Verlaufseintrag konnte nicht gespeichert werden.'
            result = self._inspect(identifier, at)
            return {'ok': True, 'item': result['item'], 'audit_warning': warning}

    def list(self, cursor=None, limit=25):
        if not 1 <= limit <= 50 or (cursor is not None and (not isinstance(cursor, str) or len(cursor) > 256)):
            raise ValueError('Ungültige Seitengröße oder Positionskennung.')
        after = cursor or ''
        # Je Index eine feste Scan-Grenze; Vereinigung und Weiterlauf nach gescannten IDs.
        produced = self.proposals.angenommene_aussagen_ab(after, 101)
        orphaned = self.episodes.quellen_mit_aussagen_ab(after, 101)
        candidates = sorted(set(produced + orphaned))
        items, scanned = [], []
        for identifier in candidates[:100]:
            scanned.append(identifier)
            inspected = self._inspect(identifier, self.clock())
            if inspected is not None:
                items.append(inspected['item'])
            if len(items) == limit:
                break
        more = bool(scanned and any(identifier > scanned[-1] for identifier in candidates))
        return {'items': items, 'next_cursor': scanned[-1] if more else None, 'truncated': more}
