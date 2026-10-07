"""Gemeinsame Mailaufnahme für ausdrückliche Einzelaufnahme und Opt-in-Zeitplan."""
import hashlib
import json
from dataclasses import replace
from contextlib import nullcontext
from typing import Callable
from . import kontakte
from .episodes import EpisodeKind, EpisodeState, EpisodeStore
from .model import Provenance, SourceType
from .source_versions import track_source


def source_key_for_message(message, source_identity=None):
    # Die serverseitige UID bindet eine Mail an ihr Konto. Message-ID ist ein
    # fremdes Headerfeld und darf keine andere Mail ersetzen können.
    uid = message.uid
    if message.account_id and uid.startswith(f"{message.account_id}:"):
        uid = uid[len(message.account_id) + 1:]
    if not uid:
        raise ValueError("Die Nachricht hat keine verlässliche Kennung.")
    if source_identity is None and getattr(message, 'provider_id', ''):
        source_identity = 'gmail:' + message.provider_id
    return "mail:" + hashlib.sha256(json.dumps([message.account_id, source_identity if source_identity is not None else uid]).encode()).hexdigest()


def remember(episodes: EpisodeStore, message, *, claims=None, source_identity=None) -> dict:
    key = source_key_for_message(message, source_identity)
    source_ref = message.message_id or f"imap:{message.uid}"
    if message.account_id:
        source_ref = f"{message.account_id}:{source_ref}"
    # Alle Beteiligten, nicht nur der Absender: An, Cc und (nur in der eigenen
    # Kopie) Bcc. Der Absender behält seine Schreibweise, damit `participants[0]`
    # bleibt, was es war.
    beteiligte = kontakte.fuer_mail(message.sender, getattr(message, "recipients", ()),
                                    eigene=getattr(message, "own_addresses", ()))
    teilnehmer = kontakte.teilnehmer_texte(beteiligte, absender_text=message.sender)
    text = message.body or message.preview
    from .mail_timeline import thread_tags, SELF, REPLY
    from .episodes import source_metadata_digest
    headers = thread_tags(message)
    tags = (["source:truncated"] if message.truncated else []) + headers
    head = episodes.source_head(key)
    if head:
        existing = episodes.get(head)
        # Header enrichment is advisory metadata, not a replacement source.
        old = existing.to_dict()
        old['tags'] = [t for t in existing.tags if not t.startswith((SELF, REPLY))]
        incoming = {'kind': EpisodeKind.MESSAGE.value, 'title': message.subject or '(kein Betreff)',
                    'occurred_at': message.date.isoformat() if message.date else None,
                    'participants': teilnehmer, 'tags': [t for t in tags if not t.startswith((SELF, REPLY))]}
        from .episodes import digest_of
        if existing.digest == digest_of(text) and source_metadata_digest(old) == source_metadata_digest(incoming):
            if existing.state is not EpisodeState.IGNORED:
                if not existing.contacts and beteiligte:
                    existing = episodes.add_contacts(existing.id, beteiligte, teilnehmer)
                existing = episodes.add_mail_headers(existing.id, headers)
            return _with_attachments(episodes, message, key, beteiligte, teilnehmer, claims,
                                     {'episode': existing.to_dict(), 'new': False, 'changed': False})
    vorhanden = _ohne_beteiligte_gespeichert(episodes, key, text)
    if vorhanden is not None and beteiligte:
        # Dieselbe Mail, früher ohne Empfänger aufgenommen: ergänzen statt eine
        # zweite Fassung anzulegen. Der Text bleibt, wie er war. Eine vom
        # Nutzer ausgeschlossene Quelle bleibt unangetastet ausgeschlossen.
        if vorhanden.state is not EpisodeState.IGNORED:
            vorhanden = episodes.add_contacts(vorhanden.id, beteiligte, teilnehmer)
            vorhanden = episodes.add_mail_headers(vorhanden.id, headers)
        return _with_attachments(episodes, message, key, beteiligte, teilnehmer, claims,
                                 {"episode": vorhanden.to_dict(), "new": False, "changed": False})
    episode, created = episodes.record(
        EpisodeKind.MESSAGE, message.subject or "(kein Betreff)",
        text,
        Provenance(source_type=SourceType.EMAIL, source_ref=source_ref, captured_at=message.date),
        occurred_at=message.date, participants=teilnehmer, contacts=beteiligte,
        tags=tags,
        source_key=key,
    )
    changed = track_source(episodes, claims, key, episode)
    return _with_attachments(episodes, message, key, beteiligte, teilnehmer, claims,
                             {"episode": episode.to_dict(), "new": created, "changed": changed})


def _with_attachments(episodes, message, key, contacts, participants, claims, result):
    # Exclusion of the original also prevents an unchanged capture from reviving its attachments.
    from .anhaenge import aufnehmen
    source_ref = message.message_id or f"imap:{message.uid}"
    if message.account_id:
        source_ref = f"{message.account_id}:{source_ref}"
    result['anhaenge'] = (aufnehmen(episodes, message, schluessel=key, herkunft=source_ref,
        beteiligte=contacts, teilnehmer=participants, claims=claims)
        if getattr(message, 'anhaenge', ()) and result['episode']['state'] != 'ignored' else [])
    return result


def _ohne_beteiligte_gespeichert(episodes: EpisodeStore, key: str, text: str):
    """Die Episode dieser Quelle, falls sie mit gleichem Text, aber ohne Rollen gespeichert ist."""
    from .episodes import digest_of
    kopf = episodes.source_head(key)
    if not kopf:
        return None
    episode = episodes.get(kopf)
    if episode.contacts or episode.digest != digest_of(text):
        return None
    return episode


def sync_account(
    episodes: EpisodeStore, account_id: str, reader, limit: int = 50,
    *, permitted: Callable[[], bool] = lambda: True, permission_lock=None, claims=None, screen=None, hold=None,
) -> dict:
    """Ein begrenzter Durchgang für ein bereits freigegebenes Konto.

    Bei Fehler bleibt der Cursor vor der betroffenen Nachricht. Wiederholung
    nach einem Absturz zwischen Aufnahme und Cursor erzeugt kein Duplikat.
    """
    cursor = episodes.mail_cursor(account_id)
    recorded = duplicates = filtered = 0
    gate = permission_lock if permission_lock is not None else nullcontext()
    with gate:
        if not permitted():
            return {"recorded": 0, "duplicates": 0, "cursor": cursor, "cancelled": True}
    for uid in reader.pending_uids(after=cursor, limit=limit):
        with gate:
            if not permitted():
                return {"recorded": recorded, "duplicates": duplicates, "cursor": cursor, "cancelled": True}
        message = reader.message(uid)
        if message.uid != uid:
            raise ValueError("Die gelieferte Mail passt nicht zur angefragten Kennung.")
        with gate:
            if not permitted():
                return {"recorded": recorded, "duplicates": duplicates, "cursor": cursor, "cancelled": True}
        decision = screen(message) if screen is not None else None
        # Netzabruf bleibt außerhalb der Sperre. Entzug und letzter
        # Schreibabschnitt müssen beim Aufrufer dieselbe Sperre verwenden.
        with gate:
            if not permitted():
                return {"recorded": recorded, "duplicates": duplicates, "cursor": cursor, "cancelled": True}
            qualified = replace(message, account_id=account_id, uid=f"{account_id}:{uid}")
            if decision is not None and not decision.include:
                if hold is None:raise ValueError('Prüfbereich fehlt.')
                hold(qualified, decision)
                result = {'new':False}
                filtered += 1
            else:
                result = remember(episodes, qualified, claims=claims)
            episodes.advance_mail_cursor(account_id, cursor, uid)
        cursor = uid
        recorded += int(result['new'])
        duplicates += int(not result['new'] and (decision is None or decision.include))
    return {"recorded": recorded, "duplicates": duplicates, "cursor": cursor, **({"filtered":filtered} if screen is not None else {})}
