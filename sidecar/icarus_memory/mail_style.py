"""Stilgedächtnis für Mailantworten: der eigene Ton je Person, je Kreis und allgemein (Paket B5, Oktober 2026).

Woher die Regeln kommen: aus **eigenen gesendeten Mails** an genau diese Adresse im selben Konto (Kontakt `von`
mit `ich`, einziger Empfänger; `EpisodeStore.gesendete_an`) und aus ausdrücklich bestätigten eigenen Schreibbelegen.
Aus beidem entsteht ein **Vorschlag** mit Belegen („In 7 von 7 Mails an Anna: Du, kurz, Gruß „Viele Grüße““); erst die
Bestätigung mit einem Klick macht ihn zur Regel. Nur Einstimmigkeit zählt: gemischtes Du/Sie ergibt keine Anrede,
verschiedene Grußformeln keinen Gruß. Zitierter Verlauf wird abgeschnitten (`kreis._ZITAT`): Fremdtext ist nie der
eigene Ton. Mails an mehrere Empfänger belegen nichts für einen einzelnen Kontakt. „Nicht übernehmen“ wird gemerkt,
bis neue Belege dazukommen.

Was die Regeln umfassen: Anrede (`address`), Länge (`length`), Emojis (`emoji`), Grußformel wörtlich (`gruss`),
Form der Anrede (`anrede_form`: Vorname, Nachname mit Titel, nur Hallo, Liebe/r, ohne) und Sprache (`sprache`).
Regeln liegen je Geltungsbereich: allgemein, Kreis (nur bestätigte Kreise, `kreis.py`) und Kontakt (Antwortadresse
plus Konto); `effective_style` schichtet allgemein → Kreis → Kontakt. Fällt ein Beleg weg (ausgeschlossen oder
durch eine neue Fassung überholt), gilt die daraus bestätigte Regel nicht mehr.

Kein Modelltraining, kein automatisches Bestätigen, keine Personenzusammenführung; der Entwurf selbst bleibt lokal
(`mail_reply_suggestions.py`).
"""
from __future__ import annotations

import hashlib
import json
import re
from email.utils import getaddresses
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeKind
from .kreis import KREISE, KREIS_TEXT, UNBESTIMMT, _ZITAT, alle_bestaetigten, bestaetigter_kreis
from .model import Kind, Provenance, Sensitivity, SourceType

DOMAIN = 'mail_style'
#: Gemerkte Ablehnung eines Vorschlags („Nicht übernehmen“): je Geltungsbereich die abgelehnten Belege.
DOMAIN_ABGELEHNT = 'mail_style_abgelehnt'
#: Höchstens so viele jüngste gesendete Mails je Adresse zählen als Beleg.
GESENDETE_HOECHSTENS = 20
#: Ab so vielen verschiedenen Texten gibt es einen Vorschlag.
MINDESTENS = 3

KreisName = Literal['innerer_kreis', 'kollegen', 'kontakte']
_STEUERZEICHEN = re.compile(r'[\x00-\x1f\x7f]')


class Rules(BaseModel):
    address: Literal['default', 'du', 'sie'] = 'default'
    length: Literal['default', 'short', 'detailed'] = 'default'
    emoji: Literal['default', 'yes', 'no'] = 'default'
    gruss: str = Field(default='', max_length=60)
    """Die Grußformel wörtlich („Viele Grüße“); leer heißt: keine Regel."""
    anrede_form: Literal['default', 'vorname', 'nachname', 'hallo', 'liebe', 'ohne'] = 'default'
    sprache: Literal['default', 'de', 'en'] = 'default'

    @field_validator('gruss')
    @classmethod
    def _gruss_eine_zeile(cls, wert: str) -> str:
        wert = wert.strip()
        if _STEUERZEICHEN.search(wert):
            raise ValueError('Die Grußformel ist eine Zeile ohne Steuerzeichen.')
        return '' if wert == 'default' else wert


class ProfileIn(BaseModel):
    scope: Literal['global', 'contact']
    rules: Rules
    evidence_ids: list[str] = Field(default_factory=list, max_length=2 * GESENDETE_HOECHSTENS)


class KreisProfileIn(BaseModel):
    rules: Rules
    evidence_ids: list[str] = Field(default_factory=list, max_length=400)


class AblehnenIn(BaseModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=400)


class ExampleIn(BaseModel):
    text: str = Field(min_length=10, max_length=5000)
    original_suggestion: str | None = Field(default=None, max_length=5000)
    own_text_confirmed: Literal[True]


def contact(message):
    addresses = getaddresses([message.reply_to or message.sender])
    if len(addresses) != 1 or not re.fullmatch(r'[^\s@,<>]+@[^\s@,<>]+\.[^\s@,<>]+', addresses[0][1]):
        raise HTTPException(422, 'Keine eindeutige Kontaktadresse für das Stilgedächtnis.')
    address = addresses[0][1].casefold()
    key = hashlib.sha256(json.dumps([message.account_id, address]).encode()).hexdigest()
    return key, address


# -- Belege ----------------------------------------------------------------------------------------------------------

def _examples(app, key):
    """Bestätigte eigene Schreibbelege dieses Kontakts: gezielt über die Marke, ohne überholte Fassungen (Befund 1)."""
    episodes = getattr(app.state, 'episodes', None)
    if episodes is None or not hasattr(episodes, 'geltende_mit_marke'):
        return []
    return episodes.geltende_mit_marke(f'mail-style:{key}')


def _gesendete(app, account_id, address):
    """Eigene gesendete Mails an genau diese Adresse; ohne `account_id` aus allen Konten (Kreis)."""
    episodes = getattr(app.state, 'episodes', None)
    if episodes is None or not hasattr(episodes, 'gesendete_an'):
        return []
    return episodes.gesendete_an(account_id, address, GESENDETE_HOECHSTENS)


def eigener_text(text: str) -> str:
    """Der eigene Teil einer Mail: vor dem zitierten Verlauf. Fremdtext darf nie in eine Regel."""
    text = text or ''
    return (_ZITAT.split(text, maxsplit=1)[0] if _ZITAT.search(text) else text).strip()


def _beleg(episode) -> dict[str, Any]:
    return {'id': episode.id, 'title': episode.title, 'occurred_at': episode.reference_time().isoformat(),
            'text': eigener_text(episode.body)[:400]}


# -- Regeln aus Texten ------------------------------------------------------------------------------------------------

_DU = re.compile(r'(?<![\wäöüß])(?:du|dir|dich|dein|deine|deinen|deinem|deiner)(?![\wäöüß])', re.I)
_SIE = re.compile(r'(?<![\wäöüß])(?:Sie|Ihnen|Ihre|Ihren|Ihrem|Ihrer)(?![\wäöüß])|(?i:sehr geehrte)')
_EMOJI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
#: Eine ganze Schlusszeile, die eine Grußformel ist (ohne Satzzeichen am Ende). Nur solche Zeilen werden wörtlich
#: zur Regel; freier Text aus einer Mail gelangt so nie in den Systemhinweis.
_GRUSS = re.compile(
    r'(?:(?:viele|liebe|herzliche|beste|schöne|sonnige|freundliche|ganz liebe) grüße(?: aus [\wäöüß\-]+)?'
    r'|(?:mit )?(?:freundlichen|besten|lieben|herzlichen|freundlichem) grü(?:ß|ss)e?n?'
    r'|gruß|grüße|lg|vg|mfg|glg|vlg|alles liebe|alles gute|bis bald|bis dann|bis morgen|bis gleich|bis später|mach.s gut'
    r'|(?:best|kind|warm|warmest) regards|regards|cheers|(?:many )?thanks|thank you|take care|all the best|best|yours)',
    re.I)
_ANREDE_NACHNAME = re.compile(r'^(?:sehr geehrte[rs]?|guten (?:tag|morgen|abend)|hallo|hi|liebe[rs]?|dear|moin)\s+'
                              r'(?:frau|herrn?|mr|mrs|ms|dr|prof|familie)\b', re.I)
_ANREDE_LIEBE = re.compile(r'^(?:liebe[rs]?)\s+\S', re.I)
_ANREDE_VORNAME = re.compile(r'^(?i:hallo|hi|hey|moin|servus|huhu|hola|dear|ciao|guten (?:tag|morgen|abend))\s+'
                             r'[A-ZÄÖÜ][\wäöüß\-]*(?:\s+[A-ZÄÖÜ][\wäöüß\-]*)?$')
_ANREDE_HALLO = re.compile(r'^(?:hallo|hi|hey|moin|servus|huhu|hola|guten (?:tag|morgen|abend))(?![\wäöüß])', re.I)
_WORT = re.compile(r"[\wäöüß']+", re.I)
_DE = frozenset('und der die das ich du nicht ist mit auf für ein eine sie wir danke grüße gruß hallo bitte dass'
                ' noch auch schon mir dir dich mich bei bis dann wie was wenn kann kannst können morgen heute'.split())
_EN = frozenset('the and you is are with for thanks please hello regards best we our your this that would could'
                ' will can tomorrow today from have has not it to of in on at'.split())


def _gruss_von(text: str) -> str:
    """Die Grußformel: die letzte Zeile des eigenen Texts, die ganz aus einer Grußformel besteht (sonst leer)."""
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    for zeile in reversed(zeilen[-6:]):
        kern = zeile.rstrip(' ,!.;:').strip()
        if kern and len(kern) <= 40 and _GRUSS.fullmatch(kern):
            return kern
    return ''


def _anrede_form_von(text: str) -> str:
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    if not zeilen:
        return 'ohne'
    anfang = re.split(r'[,!:;]', zeilen[0])[0].strip()
    if _ANREDE_NACHNAME.match(anfang):
        return 'nachname'
    if _ANREDE_LIEBE.match(anfang):
        return 'liebe'
    if _ANREDE_VORNAME.match(anfang):
        return 'vorname'
    if _ANREDE_HALLO.match(anfang):
        return 'hallo'
    return 'ohne'


def _sprache_von(text: str) -> str:
    woerter = [w.casefold() for w in _WORT.findall(text)]
    de = sum(w in _DE for w in woerter)
    en = sum(w in _EN for w in woerter)
    if de >= 2 and de > en:
        return 'de'
    if en >= 2 and en > de:
        return 'en'
    return ''


def _einstimmig(werte: list[str]) -> str:
    """Der eine Wert, den alle Texte tragen; sonst leer."""
    return werte[0] if werte and all(w == werte[0] for w in werte) and werte[0] else ''


def regeln_aus(texte: list[str]) -> dict[str, str]:
    """Beobachtbare, wiederholbare Formmerkmale aus eigenen Texten; nie Anweisungen aus einer Mail. Rein."""
    rules = Rules().model_dump()
    if not texte:
        return rules
    informal = [bool(_DU.search(t)) for t in texte]
    formal = [bool(_SIE.search(t)) for t in texte]
    if all(informal) and not any(formal):
        rules['address'] = 'du'
    elif all(formal) and not any(informal):
        rules['address'] = 'sie'
    if all(len(t.split()) <= 80 for t in texte):
        rules['length'] = 'short'
    elif all(len(t.split()) >= 150 for t in texte):
        rules['length'] = 'detailed'
    emoji = [bool(_EMOJI.search(t)) for t in texte]
    if all(emoji):
        rules['emoji'] = 'yes'
    elif not any(emoji):
        rules['emoji'] = 'no'
    gruesse = [_gruss_von(t) for t in texte]
    if _einstimmig([g.casefold() for g in gruesse]):
        rules['gruss'] = gruesse[0]
    anrede = _einstimmig([_anrede_form_von(t) for t in texte])
    if anrede:
        rules['anrede_form'] = anrede
    sprache = _einstimmig([_sprache_von(t) for t in texte])
    if sprache:
        rules['sprache'] = sprache
    return rules


def _ohne_regel(rules: dict[str, str]) -> bool:
    return all(v in ('default', '') for v in rules.values())


def _texte(examples, gesendete) -> tuple[list[str], list[str]]:
    """Verschiedene Texte (Leerraum gleichgültig) und die Kennungen der Belege, die sie tragen."""
    unique: dict[str, Any] = {}
    for e in list(examples) + list(gesendete):
        eigen = eigener_text(e.body)
        schluessel = re.sub(r'\s+', ' ', eigen).strip()
        if schluessel and schluessel not in unique:
            unique[schluessel] = e
    return [eigener_text(e.body) for e in unique.values()], [e.id for e in unique.values()]


def _proposal(examples, gesendete) -> dict[str, Any] | None:
    texte, ids = _texte(examples, gesendete)
    if len(texte) < MINDESTENS:
        return None
    rules = regeln_aus(texte)
    if _ohne_regel(rules):
        return None
    return {'rules': rules, 'evidence_ids': ids, 'gesendet': len(gesendete), 'belege': len(examples)}


def _kreis_proposal(je_person: dict[str, list]) -> dict[str, Any] | None:
    """Einstimmigkeit über die Kontakte eines Kreises: eine Regel gilt nur, wenn jeder Kontakt mit Mails sie trägt."""
    je_kontakt = []
    ids: list[str] = []
    for gesendete in je_person.values():
        texte, kennungen = _texte([], gesendete)
        if not texte:
            continue
        je_kontakt.append(regeln_aus(texte))
        ids += kennungen
    if not je_kontakt or len(ids) < MINDESTENS:
        return None
    rules = Rules().model_dump()
    for feld in rules:
        werte = [r[feld] for r in je_kontakt]
        if _einstimmig([w.casefold() for w in werte]) and werte[0] not in ('default', ''):
            rules[feld] = werte[0]
    if _ohne_regel(rules):
        return None
    return {'rules': rules, 'evidence_ids': ids, 'gesendet': len(ids), 'belege': 0, 'personen': len(je_kontakt)}


# -- Gemerkte Ablehnung („Nicht übernehmen“) -------------------------------------------------------------------------

def _abgelehnte(app, scope_key: str) -> set[str]:
    if not hasattr(app.state, 'store'):
        return set()
    ids: set[str] = set()
    for a in app.state.store.usable():
        data = a.structured or {}
        if data.get('domain') == DOMAIN_ABGELEHNT and data.get('scope_key') == scope_key:
            ids.update(data.get('evidence_ids', []))
    return ids


def _mit_ablehnung(app, scope_key: str, proposal: dict | None, *, bestaetigt_unter: tuple[str, ...] = ()) -> tuple[dict | None, bool]:
    """Ein abgelehnter Vorschlag bleibt verborgen, solange kein neuer Beleg dazukommt; ein schon übernommener (gleiche
    Belege, gleiche Regeln, unter einem der Geltungsbereiche `bestaetigt_unter`) wird nicht noch einmal vorgelegt."""
    if proposal and set(proposal['evidence_ids']) <= _abgelehnte(app, scope_key):
        return None, True
    for bereich in bestaetigt_unter or (scope_key,):
        profil = _profile_for(app, bereich)
        if proposal and profil and set(profil['evidence_ids']) == set(proposal['evidence_ids']) and profil['rules'] == proposal['rules']:
            return None, False
    return proposal, False


def _ablehnen(app, scope_key: str, label: str, ids: list[str], proposal: dict | None) -> None:
    if not proposal or set(ids) != set(proposal['evidence_ids']):
        raise HTTPException(409, 'Der Vorschlag ist nicht mehr aktuell. Bitte neu laden.')
    prior = [a.id for a in app.state.store.usable()
             if (a.structured or {}).get('domain') == DOMAIN_ABGELEHNT and a.structured.get('scope_key') == scope_key]
    app.state.store.record(f'Stilvorschlag nicht übernommen ({label})', Kind.PREFERENCE,
                           Provenance(source_type=SourceType.USER_STATED, source_ref='ui:mail-style'),
                           sensitivity=Sensitivity.SENSITIVE, supersedes=prior,
                           structured={'domain': DOMAIN_ABGELEHNT, 'scope_key': scope_key, 'evidence_ids': list(ids)})


# -- Bestätigte Regeln ------------------------------------------------------------------------------------------------

def _belege_gelten(app, ids: list[str]) -> bool:
    """Alle Belege einer Regel sind da, nicht ausgeblendet und nicht durch eine neue Fassung überholt."""
    episodes = app.state.episodes
    for eid in ids:
        try:
            if episodes.get(eid).state in AUSGEBLENDETE_ZUSTAENDE:
                return False
        except Exception:
            return False
    return not (ids and hasattr(episodes, 'ueberholte_fassungen') and episodes.ueberholte_fassungen(ids))


def _profile_for(app, scope_key: str) -> dict[str, Any] | None:
    if not hasattr(app.state, 'store') or not hasattr(app.state, 'episodes'):
        return None
    gefunden = None
    for a in app.state.store.usable():
        data = a.structured or {}
        if data.get('domain') != DOMAIN or data.get('scope_key') != scope_key:
            continue
        if _belege_gelten(app, data.get('evidence_ids', [])):
            gefunden = {'id': a.id, 'rules': data['rules'], 'evidence_ids': data.get('evidence_ids', [])}
    return gefunden


def _profiles(app, key, kreis: str | None = None):
    return {'global': _profile_for(app, 'global'),
            'kreis': _profile_for(app, f'kreis:{kreis}') if kreis else None,
            'contact': _profile_for(app, key)}


def _kreis_von(app, address: str) -> str | None:
    """Der bestätigte Kreis der Person hinter der Adresse, sonst nichts. Ein Vorschlag zählt nicht."""
    episodes = getattr(app.state, 'episodes', None)
    if episodes is None or not hasattr(episodes, '_conn'):
        return None
    kreis = bestaetigter_kreis(episodes, f'person:a:{address}')
    return None if kreis == UNBESTIMMT else kreis


def effective_style(app, message):
    """Die wirksamen Regeln: allgemein → Kreis → Kontakt; nur bestätigte, nur mit geltenden Belegen."""
    try:
        key, address = contact(message)
    except HTTPException:
        return {}
    profiles = _profiles(app, key, _kreis_von(app, address))
    rules: dict[str, str] = {}
    for scope in ('global', 'kreis', 'contact'):
        if profiles[scope]:
            rules.update({k: v for k, v in profiles[scope]['rules'].items() if v not in ('default', '')})
    return rules


def tone_hint(app, message) -> dict[str, Any]:
    """Für den Ort, wo der Entwurf entsteht: Ist ein Kontaktstil bestätigt, und aus wie vielen gesendeten Mails liegt
    ein noch unbestätigter Vorschlag vor? Kein Beleg, keine Liste; die Zeile im Schreibstil zeigt den Rest."""
    try:
        key, address = contact(message)
    except HTTPException:
        return {'bestaetigt': False, 'gesendet': 0}
    if not hasattr(app.state, 'store') or not hasattr(app.state, 'episodes'):
        return {'bestaetigt': False, 'gesendet': 0}
    proposal, _ = _mit_ablehnung(app, key, _proposal(_examples(app, key), _gesendete(app, message.account_id, address)),
                                 bestaetigt_unter=(key, 'global'))
    return {'bestaetigt': _profile_for(app, key) is not None, 'gesendet': proposal['gesendet'] if proposal else 0}


def _confirm(app, scope_key: str, label: str, rules: Rules, ids: list[str], proposal: dict | None) -> None:
    ids = list(dict.fromkeys(ids))
    if ids and (not proposal or set(ids) != set(proposal['evidence_ids']) or rules.model_dump() != proposal['rules']):
        raise HTTPException(409, 'Der Lernvorschlag ist nicht mehr aktuell. Bitte neu laden.')
    prior = [a.id for a in app.state.store.usable()
             if (a.structured or {}).get('domain') == DOMAIN and a.structured.get('scope_key') == scope_key]
    app.state.store.record(f'Bestätigter E-Mail-Schreibstil ({label}): {json.dumps(rules.model_dump(), ensure_ascii=False)}',
        Kind.PREFERENCE, Provenance(source_type=SourceType.USER_STATED, source_ref='ui:mail-style'),
        sensitivity=Sensitivity.SENSITIVE, supersedes=prior,
        structured={'domain': DOMAIN, 'scope_key': scope_key, 'rules': rules.model_dump(), 'evidence_ids': ids})


def _retract(app, scope_key: str) -> None:
    for a in app.state.store.usable():
        if (a.structured or {}).get('domain') == DOMAIN and a.structured.get('scope_key') == scope_key:
            app.state.store.retract(a.id)


# -- Routen ----------------------------------------------------------------------------------------------------------

def register_mail_style(app, guard):
    def resolve(uid):
        mail = app.state.mail
        try:
            message = mail.message(uid)
        except Exception as exc:
            raise HTTPException(404, 'Mail nicht verfügbar.') from exc
        if message.uid != uid or app.state.mail is not mail:
            raise HTTPException(409, 'Mailkonto wurde geändert.')
        return mail, message, contact(message)

    def ensure_current(mail, message=None):
        if message is not None:
            from .mail_reply_suggestions import _fingerprint
            try:
                latest = mail.message(message.uid)
            except Exception as exc:
                raise HTTPException(409, "Die ursprüngliche Mail ist nicht mehr verfügbar.") from exc
            if _fingerprint(latest) != _fingerprint(message):
                raise HTTPException(409, "Die Mail wurde geändert. Bitte neu laden.")
        if app.state.mail is not mail:
            raise HTTPException(409, 'Mailkonto wurde geändert.')

    def proposal_for(key, address, account_id):
        examples = _examples(app, key)
        gesendete = _gesendete(app, account_id, address)
        proposal, abgelehnt = _mit_ablehnung(app, key, _proposal(examples, gesendete), bestaetigt_unter=(key, 'global'))
        return examples, gesendete, proposal, abgelehnt

    def state(key, address, account_id):
        examples, gesendete, proposal, abgelehnt = proposal_for(key, address, account_id)
        kreis = _kreis_von(app, address)
        return {'contact': address,
                'kreis': {'kreis': kreis, 'kreis_text': KREIS_TEXT[kreis]} if kreis else None,
                'profiles': _profiles(app, key, kreis),
                'examples': [{'id': e.id, 'text': e.body, 'created_at': e.reference_time().isoformat()} for e in examples],
                'gesendete': [_beleg(e) for e in gesendete],
                'proposal': proposal, 'abgelehnt': abgelehnt}

    @app.get('/api/v1/messages/{uid}/style', dependencies=guard)
    def get_style(uid: str):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail)
            return state(key, address, message.account_id)

    @app.post('/api/v1/messages/{uid}/style/examples', dependencies=guard)
    def add_example(uid: str, body: ExampleIn):
        mail, message, (key, address) = resolve(uid)
        text = body.text.strip()
        normalize = lambda s: re.sub(r'\s+', ' ', s).strip()
        if len(text) < 10 or (body.original_suggestion and normalize(text) == normalize(body.original_suggestion)):
            raise HTTPException(422, 'Unveränderte KI-Vorschläge sind keine eigenen Schreibbelege.')
        with app.state.conversation_lock:
            ensure_current(mail, message)
            if len(_examples(app, key)) >= 20:
                raise HTTPException(409, 'Bitte zuerst einen der 20 Schreibbelege zurücknehmen.')
            digest = hashlib.sha256(normalize(text).encode()).hexdigest()
            source = f'mail-style:{key}:{digest}'
            episodes = app.state.episodes
            vorher = episodes.source_head(source)
            episode, neu = episodes.record(EpisodeKind.MESSAGE, 'Eigener Schreibbeleg', text,
                Provenance(source_type=SourceType.USER_STATED, source_ref=source, verbatim=text),
                tags=[f'mail-style:{key}'], source_key=source)
            if neu and vorher != episode.id:
                # Derselbe Beleg mit anderem Leerraum ersetzt die Fassung, statt daneben zu stehen.
                episodes.advance_source_head(source, vorher, episode.id)
            return state(key, address, message.account_id)

    @app.put('/api/v1/messages/{uid}/style', dependencies=guard)
    def save_style(uid: str, body: ProfileIn):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            _, _, proposal, _ = proposal_for(key, address, message.account_id)
            scope_key = 'global' if body.scope == 'global' else key
            label = 'allgemein' if body.scope == 'global' else f'{address} (Konto {message.account_id})'
            _confirm(app, scope_key, label, body.rules, body.evidence_ids, proposal)
            return state(key, address, message.account_id)

    @app.post('/api/v1/messages/{uid}/style/ablehnen', dependencies=guard)
    def dismiss_style(uid: str, body: AblehnenIn):
        """„Nicht übernehmen“: der Vorschlag mit genau diesen Belegen wird gemerkt und nicht mehr gezeigt, bis neue
        Belege dazukommen. Es entsteht keine Regel."""
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            _, _, proposal, _ = proposal_for(key, address, message.account_id)
            _ablehnen(app, key, f'{address} (Konto {message.account_id})', body.evidence_ids, proposal)
            return state(key, address, message.account_id)

    @app.delete('/api/v1/messages/{uid}/style/examples/{example_id}', dependencies=guard)
    def remove_example(uid: str, example_id: str):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            if example_id not in {e.id for e in _examples(app, key)}:
                raise HTTPException(404, 'Schreibbeleg nicht gefunden.')
            app.state.episodes.ignore(example_id)
            # Retract derived preferences too, so general recall cannot reuse them.
            for a in app.state.store.usable():
                if (a.structured or {}).get('domain') == DOMAIN and example_id in a.structured.get('evidence_ids', []):
                    app.state.store.retract(a.id)
            return state(key, address, message.account_id)

    @app.delete('/api/v1/messages/{uid}/style/{scope}', dependencies=guard)
    def reset_style(uid: str, scope: Literal['global', 'contact']):
        mail, message, (key, address) = resolve(uid)
        with app.state.conversation_lock:
            ensure_current(mail, message)
            _retract(app, 'global' if scope == 'global' else key)
            return state(key, address, message.account_id)

    # -- Kreis: der Ton an alle bestätigten Personen eines Kreises ----------------------------------------------------

    def kreis_state(kreis: str) -> dict[str, Any]:
        episodes = app.state.episodes
        personen = sorted(s[len('person:a:'):] for s, k in alle_bestaetigten(episodes).items()
                          if k == kreis and s.startswith('person:a:'))
        je_person = {adresse: _gesendete(app, None, adresse) for adresse in personen}
        proposal, abgelehnt = _mit_ablehnung(app, f'kreis:{kreis}', _kreis_proposal(je_person))
        gesendete = sorted((e for mails in je_person.values() for e in mails), key=lambda e: e.reference_time(), reverse=True)
        return {'kreis': kreis, 'kreis_text': KREIS_TEXT[kreis], 'personen': len(personen),
                'profile': _profile_for(app, f'kreis:{kreis}'), 'proposal': proposal, 'abgelehnt': abgelehnt,
                'gesendete': [_beleg(e) for e in gesendete[:2 * GESENDETE_HOECHSTENS]]}

    @app.get('/api/v1/stil/kreise', dependencies=guard)
    def get_kreise():
        """Je bestätigtem Kreis: bestätigte Regel, Vorschlag aus den gesendeten Mails an seine Personen, Belege."""
        with app.state.conversation_lock:
            return {'kreise': [kreis_state(k) for k in KREISE]}

    @app.put('/api/v1/stil/kreis/{kreis}', dependencies=guard)
    def save_kreis_style(kreis: KreisName, body: KreisProfileIn):
        with app.state.conversation_lock:
            proposal = kreis_state(kreis)['proposal']
            _confirm(app, f'kreis:{kreis}', f'Kreis {KREIS_TEXT[kreis]}', body.rules, body.evidence_ids, proposal)
            return kreis_state(kreis)

    @app.delete('/api/v1/stil/kreis/{kreis}', dependencies=guard)
    def reset_kreis_style(kreis: KreisName):
        with app.state.conversation_lock:
            _retract(app, f'kreis:{kreis}')
            return kreis_state(kreis)

    @app.post('/api/v1/stil/kreis/{kreis}/ablehnen', dependencies=guard)
    def dismiss_kreis_style(kreis: KreisName, body: AblehnenIn):
        with app.state.conversation_lock:
            proposal = kreis_state(kreis)['proposal']
            _ablehnen(app, f'kreis:{kreis}', f'Kreis {KREIS_TEXT[kreis]}', body.evidence_ids, proposal)
            return kreis_state(kreis)


__all__ = ['DOMAIN', 'Rules', 'contact', 'effective_style', 'eigener_text', 'regeln_aus', 'register_mail_style',
           'tone_hint']
