"""Alles zu einer Person: Umfang, Auskunft und Löschen (Persona-Prüfung, Paket P, D7, 27.10.2026).

Bis 1.0.29 gab es weder Löschen noch Export je Person; das Auskunftsrecht (Art. 15 DSGVO) und das Recht auf Löschung
(Art. 17) waren in Kingfisher nicht bedienbar. Dieses Modul beantwortet drei Fragen an einer Stelle, damit Auskunft,
Rückfrage und Löschen nie auseinanderlaufen:

* **Was gehört zu ihr?** (`umfang`) Die Quellen, in denen sie beteiligt ist (Absender, Empfänger, Gast, genannt ohne
  Adresse), getrennt nach „nur sie“ (außer dir niemand) und „geteilt“; bestätigtes Wissen über sie; Vorschläge aus ihren
  Quellen oder über sie; Aufgaben von ihr oder für sie; Zusammenführungen und Schreibweisen; Kreis, Art der Akte,
  Entscheidungen in ihrer Akte; Vermerke im Logbuch, Befunde, Zusammenfassungen, die sie nennen.
* **Auskunft** (`auskunft`, `auskunft_zip`): eine Datei für Menschen (HTML) und eine für Maschinen (JSON) in einem
  ZIP, nur auf den Rechner. Aus geteilten Quellen nur die Zeilen, die sie nennen, fremde Adressen darin unkenntlich; wer
  sonst beteiligt war, steht nur als Zahl da.
* **Löschen** (`loeschen`), nach einer Rückfrage in der Oberfläche:
  - Wissen, Vorschläge, Aufgaben, Zusammenführungen, Schreibweisen, Bezüge, Kreis und personenbezogene Vermerke fallen
    weg (auch aus Verläufen, die sonst nur anhängen: Aufgabenverlauf, Logbuch; nur hier, nur auf ausdrücklichen Wunsch).
  - Quellen, die nur sie betreffen, werden aus Kingfisher entfernt, samt Anlagen, Suchindex, Bedeutungssuche,
    Einordnung und Bezügen. Im Postfach und im Kalender bleiben sie.
  - Geteilte Quellen bleiben, ohne sie als Beteiligte; ihr Text bleibt unverändert.
  - Zuerst entsteht der Sperrvermerk (`person_sperre.py`), damit das nächste Einlesen sie nicht wieder anlegt.
  - Was bleibt und warum, steht in `bleibt` und in der Rückfrage: deine Gespräche mit Kingfisher, das Protokoll
    dessen, was Kingfisher in deinem Namen getan hat, Projekte und ältere Sicherungen.

Die Regel des Gedächtnisses gilt weiter: Löschen schreibt keinen Fakt, es nimmt nur weg; Verdichtung schlägt danach
weiter nur vor. Nichts davon geht nach draußen.
"""
from __future__ import annotations

import html
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from . import identitaet, personen
from .episodes import EpisodeKind, EpisodeState, mail_address
from .identitaet import name_anker, name_schluessel

FORMAT = 'kingfisher-auskunft-v1'
#: So viele Zeilen je geteilter Quelle, so lang je Zeile; der volle Text nur bei Quellen, die nur sie betreffen.
AUSZUG_ZEILEN = 6
AUSZUG_ZEICHEN = 400
VOLLTEXT_ZEICHEN = 20000
_ADRESSE = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', re.UNICODE)


class PersonNichtGefunden(LookupError):
    pass


@dataclass
class Umfang:
    """Was Kingfisher über eine Person hat. Nur Kennungen und Zahlen, keine Inhalte."""

    angabe: str
    anzeige: str
    adressen: list[str]
    namen: list[str]
    #: Kennungen, unter denen Wissen und Gruppen sie führen (Graph, Zusammenführung, ausdrückliche Entität).
    kennungen: list[str] = field(default_factory=list)
    #: Akten-Schlüssel (`person:a:<adresse>`, `person:n:<name>`).
    sachen: list[str] = field(default_factory=list)
    nur_ihre: list[str] = field(default_factory=list)
    geteilte: list[str] = field(default_factory=list)
    aussagen: list[str] = field(default_factory=list)
    vorschlaege: list[str] = field(default_factory=list)
    offene_vorschlaege: int = 0
    aufgaben: list[str] = field(default_factory=list)
    zusammenfuehrungen: list[str] = field(default_factory=list)
    entitaeten: list[str] = field(default_factory=list)
    vermerke: list[int] = field(default_factory=list)
    befunde: list[str] = field(default_factory=list)
    zusammenfassungen: list[str] = field(default_factory=list)
    #: Was bleibt (nur gezählt, nicht gelöscht).
    gespraeche: int = 0
    projekte: list[str] = field(default_factory=list)

    def zahlen(self) -> dict[str, int]:
        return {'quellen_nur_ihre': len(self.nur_ihre), 'quellen_geteilt': len(self.geteilte),
                'aussagen': len(self.aussagen), 'vorschlaege': len(self.vorschlaege),
                'offene_vorschlaege': self.offene_vorschlaege, 'aufgaben': len(self.aufgaben),
                'zusammenfuehrungen': len(self.zusammenfuehrungen), 'schreibweisen': max(0, len(self.namen) - 1),
                'adressen': len(self.adressen), 'vermerke': len(self.vermerke) + len(self.befunde),
                'zusammenfassungen': len(self.zusammenfassungen), 'gespraeche': self.gespraeche,
                'projekte': len(self.projekte)}


# -- Wer ist gemeint -------------------------------------------------------------------------------------------


def _eigene(app: Any) -> list[str]:
    return identitaet.eigene_adressen(getattr(app.state, 'settings', None))


def _person(app: Any, angabe: str) -> personen.Person:
    try:
        mensch = personen.eine(angabe, episodes=app.state.episodes, tasks=app.state.tasks, store=app.state.store,
                               workspace=app.state.workspace, jetzt=datetime.now().astimezone(), eigene=_eigene(app),
                               confirmed_merges=app.state.claims.person_merges.list())
    except personen.Mehrdeutig:
        raise
    if mensch is None:
        raise PersonNichtGefunden(f'In deinen Aufzeichnungen kommt „{angabe}“ nicht vor.')
    return mensch


class _Treffer:
    """Ob eine Nennung diese Person meint: mit Adresse über die Adresse, ohne über einen Namen, den keine fremde
    Adresse trägt (sonst wäre es geraten; `identitaet.py`)."""

    def __init__(self, adressen: Iterable[str], namen: Iterable[str], fremde_namen: set[str]) -> None:
        self.adressen = {a.casefold() for a in adressen if a}
        self.namen = {name_schluessel(n) for n in namen if name_schluessel(n)} - fremde_namen

    def nennung(self, adresse: str, name: str) -> bool:
        if adresse:
            return adresse.casefold() in self.adressen
        return bool(name) and name_schluessel(name) in self.namen

    def text(self, wert: str) -> bool:
        adresse = mail_address(wert)
        return self.nennung(adresse, '' if adresse else wert)

    def kontakt(self, eintrag: dict[str, Any]) -> bool:
        if eintrag.get('ich'):
            return False
        adresse = str(eintrag.get('adresse') or '').casefold()
        return self.nennung(adresse, '' if adresse else str(eintrag.get('name') or ''))


def _fremde_namen(app: Any, adressen: set[str]) -> set[str]:
    """Namensschlüssel, die (auch) eine fremde Adresse trägt: Eine bloße Namensnennung wäre dann nicht eindeutig."""
    fremde: set[str] = set()
    try:
        alle = app.state.episodes._alle_teilnehmer(anzeigenamen=True)
    except Exception:  # noqa: BLE001 - ohne Verzeichnis gilt nur die Adresse
        alle = {}
    for adresse, eintrag in (alle or {}).items():
        if str(adresse).casefold() in adressen or not isinstance(eintrag, dict):
            continue
        for name in (eintrag.get('namen') or {}):
            if name and name_schluessel(name):
                fremde.add(name_schluessel(name))
    return fremde


def umfang(app: Any, angabe: str) -> tuple[Umfang, personen.Person]:
    """Was alles zu der Person gehört, die `angabe` meint (Adresse, Name oder „Name <adresse>“).

    Wirft `PersonNichtGefunden` oder `personen.Mehrdeutig`.
    """
    mensch = _person(app, angabe)
    adressen = sorted({a.casefold() for a in mensch.adressen if a})
    namen = list(dict.fromkeys(n for n in [mensch.anzeige or mensch.name, mensch.name, *mensch.namen] if n))
    if not adressen:
        # Ohne Adresse ist die Person ihr Name.
        namen = list(dict.fromkeys([mensch.name, *namen]))
    treffer = _Treffer(adressen, namen if not adressen else [], _fremde_namen(app, set(adressen)))
    if not adressen:
        treffer.namen = {name_schluessel(n) for n in namen if name_schluessel(n)}
    from .graph import person_id_fuer
    kennungen = {person_id_fuer('a:' + a) for a in adressen}
    sachen = {'person:a:' + a for a in adressen}
    if not adressen:
        for name in namen:
            kennungen.add(person_id_fuer('n:' + name_anker(name)))
            sachen.add('person:n:' + name_anker(name))
    if mensch.id and not mensch.id.startswith(('a:', 'n:')):
        kennungen.add(mensch.id)
    u = Umfang(angabe=angabe, anzeige=mensch.anzeige or mensch.name, adressen=adressen, namen=namen)

    claims = app.state.claims
    for eintrag in claims.person_merges.list():
        mitglieder = {m.get('id') for m in eintrag.get('members') or [] if isinstance(m, dict)}
        if mitglieder & kennungen:
            u.zusammenfuehrungen.append(eintrag['id'])
            kennungen.add(eintrag['id'])
    with claims._lock:
        for entitaet, native in claims._conn.execute(
                'SELECT entity_id, native_id FROM entity_aliases').fetchall():
            if str(native or '').casefold() in adressen:
                u.entitaeten.append(entitaet)
                kennungen.add(entitaet)
    u.entitaeten = sorted(set(u.entitaeten))
    u.kennungen = sorted(kennungen)
    u.sachen = sorted(sachen)

    _quellen_einteilen(app, u, treffer)
    _wissen_und_vorschlaege(app, u)
    _aufgaben(app, u, treffer)
    _vermerke(app, u)
    _bleibt(app, u)
    return u, mensch


def _quellen_einteilen(app: Any, u: Umfang, treffer: _Treffer) -> None:
    episodes = app.state.episodes
    eigene = _eigene(app)
    nur: list[str] = []
    geteilt: list[str] = []
    zusammen: list[str] = []
    for episode in episodes.each_episode():
        if episode.kind is EpisodeKind.SUMMARY:
            text = f'{episode.title}\n{episode.body}'.casefold()
            if any(a in text for a in u.adressen) or any(n.casefold() in text for n in u.namen if len(n) > 3):
                zusammen.append(episode.id)
            continue
        nennungen = identitaet.nennungen(episode, eigene)
        ihre = [n for n in nennungen if not n.ich and treffer.nennung(n.adresse, n.name)]
        if not ihre:
            continue
        andere = [n for n in nennungen if not n.ich and not treffer.nennung(n.adresse, n.name)]
        (geteilt if andere else nur).append(episode.id)
    # Anlagen einer Mail, die nur sie betrifft, gehören dazu.
    bekannt = set(nur)
    for episode_id in list(nur):
        for kind in episodes.mail_attachment_children(episode_id):
            if kind not in bekannt:
                bekannt.add(kind)
                nur.append(kind)
    u.nur_ihre = nur
    u.geteilte = [e for e in geteilt if e not in bekannt]
    u.zusammenfassungen = zusammen


def _wissen_und_vorschlaege(app: Any, u: Umfang) -> None:
    weg = set(u.nur_ihre)
    kennungen = set(u.kennungen)
    claims = app.state.claims
    with claims._lock:
        zeilen = claims._conn.execute('SELECT id, subject_ref, scope_ref, document FROM knowledge_claims').fetchall()
    for kennung, subjekt, umfeld, dokument in zeilen:
        try:
            daten = json.loads(dokument or '{}')
        except ValueError:
            daten = {}
        belege = {b.get('episode_id') for b in daten.get('evidence') or [] if isinstance(b, dict)}
        if ({subjekt, umfeld, daten.get('target_ref')} & kennungen) or (belege and belege <= weg):
            u.aussagen.append(kennung)
    proposals = app.state.proposals
    with proposals._lock:
        zeilen = proposals._conn.execute('SELECT id, state, document FROM proposals').fetchall()
    for kennung, zustand, dokument in zeilen:
        try:
            daten = json.loads(dokument or '{}')
        except ValueError:
            daten = {}
        belege = {b.get('episode_id') for b in daten.get('evidence') or [] if isinstance(b, dict)}
        bezug = set(daten.get('about') or []) | {daten.get('subject_ref'), daten.get('target_ref')}
        kontext = daten.get('task_context') or {}
        kontext_adresse = str((kontext.get('person') or {}).get('adresse') or '').casefold() \
            if isinstance(kontext, dict) and isinstance(kontext.get('person'), dict) else ''
        if (belege & weg) or (bezug & kennungen) or (kontext_adresse and kontext_adresse in u.adressen):
            u.vorschlaege.append(kennung)
            if zustand == 'pending':
                u.offene_vorschlaege += 1


def _aufgaben(app: Any, u: Umfang, treffer: _Treffer) -> None:
    weg = {'episode:' + e for e in u.nur_ihre}
    vorschlaege = set(u.vorschlaege)
    namen = {personen.schluessel(n) for n in u.namen}
    tasks = app.state.tasks
    with tasks._lock:
        zeilen = tasks._conn.execute('SELECT id, document FROM tasks').fetchall()
    for kennung, dokument in zeilen:
        try:
            daten = json.loads(dokument or '{}')
        except ValueError:
            continue
        person = daten.get('person') if isinstance(daten.get('person'), dict) else {}
        wartet = str(daten.get('wartet_auf') or '')
        quelle = str((daten.get('provenance') or {}).get('source_ref') or '')
        vorschlag = kennung.removeprefix('t-suggestion-') if kennung.startswith('t-suggestion-') else ''
        if (str(person.get('adresse') or '').casefold() in u.adressen and person.get('adresse')) \
                or (wartet and (treffer.text(wartet) or (not mail_address(wartet)
                                                         and personen.schluessel(wartet) in namen))) \
                or quelle in weg or vorschlag in vorschlaege:
            u.aufgaben.append(kennung)


def _passt_daten(werte: Any, sachen: set[str], namen: set[str], kennungen: set[str]) -> bool:
    if isinstance(werte, dict):
        return any(_passt_daten(v, sachen, namen, kennungen) for v in werte.values())
    if isinstance(werte, (list, tuple)):
        return any(_passt_daten(v, sachen, namen, kennungen) for v in werte)
    if isinstance(werte, str):
        return werte in sachen or werte in kennungen or werte.casefold() in namen
    return False


def _vermerke(app: Any, u: Umfang) -> None:
    sachen = set(u.sachen)
    namen = {n.casefold() for n in u.namen}
    kennungen = set(u.kennungen) | set(u.nur_ihre) | set(u.aufgaben) | set(u.vorschlaege)
    buch = getattr(app.state, 'logbuch', None)
    if buch is not None:
        with buch._lock:
            zeilen = buch._conn.execute('SELECT id, daten FROM ereignis').fetchall()
        for kennung, daten in zeilen:
            try:
                werte = json.loads(daten or '{}')
            except ValueError:
                continue
            if _passt_daten(werte, sachen, namen, kennungen):
                u.vermerke.append(int(kennung))
    befunde = getattr(app.state, 'lint_befunde', None)
    if befunde is not None:
        with befunde._lock:
            zeilen = befunde._conn.execute('SELECT id, sachen, belege FROM befund').fetchall()
        for kennung, roh_sachen, roh_belege in zeilen:
            try:
                werte = [json.loads(roh_sachen or '[]'), json.loads(roh_belege or '[]')]
            except ValueError:
                continue
            if _passt_daten(werte, sachen, namen, kennungen):
                u.befunde.append(kennung)


def _bleibt(app: Any, u: Umfang) -> None:
    gespraeche = getattr(app.state, 'conversations', None)
    muster = [a for a in u.adressen] + [n.casefold() for n in u.namen if len(n) > 3]
    if gespraeche is not None and muster:
        with gespraeche._lock:
            zeilen = gespraeche._conn.execute('SELECT conversation_id, content FROM conversation_messages').fetchall()
        u.gespraeche = len({g for g, inhalt in zeilen if any(m in str(inhalt or '').casefold() for m in muster)})
    projekte: dict[str, str] = {}
    try:
        namen = {p.id: p.name for p in app.state.workspace.projects(include_closed=True)}
    except Exception:  # noqa: BLE001
        namen = {}
    for episode_id in [*u.nur_ihre, *u.geteilte]:
        try:
            projekt = app.state.episodes.get(episode_id).project_id
        except Exception:  # noqa: BLE001
            continue
        if projekt and projekt in namen:
            projekte[projekt] = namen[projekt]
    u.projekte = sorted(projekte.values(), key=str.casefold)


# -- Auskunft ----------------------------------------------------------------------------------------------------


def _unkenntlich(text: str, eigene: set[str]) -> str:
    """Fremde Adressen in einem Auszug unkenntlich; die der Person bleiben."""
    return _ADRESSE.sub(lambda t: t.group(0) if t.group(0).casefold() in eigene else '[Adresse]', text)


def _auszug(body: str, u: Umfang, *, ganz: bool) -> list[str]:
    adressen = set(u.adressen)
    if ganz:
        text = body[:VOLLTEXT_ZEICHEN]
        return [_unkenntlich(text, adressen)] + (['[gekürzt]'] if len(body) > VOLLTEXT_ZEICHEN else [])
    muster = [a for a in adressen] + [n.casefold() for n in u.namen if len(n.strip()) > 2]
    nachname = {n.split()[-1].casefold() for n in u.namen if len(n.split()) > 1 and len(n.split()[-1]) > 3}
    zeilen = []
    for zeile in body.splitlines():
        klein = zeile.casefold()
        if any(m in klein for m in muster) or any(re.search(r'\b' + re.escape(n) + r'\b', klein) for n in nachname):
            zeilen.append(_unkenntlich(zeile.strip()[:AUSZUG_ZEICHEN], adressen))
        if len(zeilen) >= AUSZUG_ZEILEN:
            break
    return zeilen


_ARTEN = {'message': 'Mail', 'event': 'Termin', 'document': 'Dokument', 'note': 'Notiz', 'conversation': 'Gespräch',
          'transcript': 'Mitschrift'}


def _datum(wert: Any) -> str | None:
    if isinstance(wert, datetime):
        return wert.astimezone().isoformat(timespec='minutes')
    return str(wert) if wert else None


def auskunft(app: Any, angabe: str, *, jetzt: datetime | None = None) -> dict[str, Any]:
    """Alles, was Kingfisher über die Person weiß und woher, als JSON-fähiges Wörterbuch."""
    u, mensch = umfang(app, angabe)
    jetzt = jetzt or datetime.now(timezone.utc)
    episodes = app.state.episodes
    eigene = _eigene(app)
    treffer = _Treffer(u.adressen, u.namen if not u.adressen else [], set())
    if not u.adressen:
        treffer.namen = {name_schluessel(n) for n in u.namen}
    quellen = []
    for episode_id, ganz in [(e, True) for e in u.nur_ihre] + [(e, False) for e in u.geteilte]:
        try:
            episode = episodes.get(episode_id)
        except Exception:  # noqa: BLE001
            continue
        nennungen = identitaet.nennungen(episode, eigene)
        rollen = sorted({n.rolle for n in nennungen if not n.ich and treffer.nennung(n.adresse, n.name)})
        weitere = len({(n.adresse or name_schluessel(n.name)) for n in nennungen
                       if not n.ich and not treffer.nennung(n.adresse, n.name)})
        quellen.append({
            'kennung': episode.id, 'art': _ARTEN.get(episode.kind.value, episode.kind.value),
            'herkunft': episode.provenance.source_type.value,
            'titel': _unkenntlich(episode.title or '', set(u.adressen)),
            'datum': _datum(episode.occurred_at or episode.recorded_at),
            'aufgenommen': _datum(episode.recorded_at), 'rolle': rollen,
            'nur_mit_dir': ganz, 'weitere_beteiligte': weitere,
            'ausgeschlossen': episode.state is EpisodeState.IGNORED,
            'auszug': _auszug(episode.body or '', u, ganz=ganz),
        })
    quellen.sort(key=lambda q: q['datum'] or '', reverse=True)

    def claim_daten(kennung: str) -> dict[str, Any] | None:
        try:
            claim = app.state.claims.get(kennung).to_dict()
        except Exception:  # noqa: BLE001
            return None
        return {'aussage': claim.get('statement'), 'beziehung': claim.get('predicate'), 'wert': claim.get('value'),
                'stand': claim.get('status'), 'seit': claim.get('created_at'),
                'belege': [b.get('episode_id') for b in claim.get('evidence') or [] if isinstance(b, dict)]}

    wissen = [d for d in (claim_daten(k) for k in u.aussagen) if d]
    vorschlaege = []
    for kennung in u.vorschlaege:
        try:
            vorschlag = app.state.proposals.get(kennung).to_dict()
        except Exception:  # noqa: BLE001
            continue
        vorschlaege.append({'vorschlag': vorschlag.get('statement'), 'art': vorschlag.get('kind'),
                            'stand': vorschlag.get('state'), 'erstellt': vorschlag.get('created_at'),
                            'belege': [b.get('episode_id') for b in vorschlag.get('evidence') or []
                                       if isinstance(b, dict)]})
    aufgaben = []
    for kennung in u.aufgaben:
        aufgabe = app.state.tasks.get(kennung)
        if aufgabe is None:
            continue
        daten = aufgabe.to_dict()
        aufgaben.append({'titel': daten.get('title'), 'stand': daten.get('status'), 'faellig': daten.get('due'),
                         'wartet_auf': daten.get('wartet_auf'), 'erstellt': daten.get('created_at'),
                         'quelle': (daten.get('provenance') or {}).get('source_ref')})
    zusammen = []
    for eintrag in app.state.claims.person_merges.list():
        if eintrag['id'] in u.zusammenfuehrungen:
            zusammen.append({'name': eintrag.get('label'), 'seit': eintrag.get('created_at'),
                             'aufgehoben': eintrag.get('undone_at'),
                             'mitglieder': [m.get('label') for m in eintrag.get('members') or [] if isinstance(m, dict)]})
    with episodes._lock:
        kreis = [dict(zip(('sache', 'kreis', 'bestaetigt_am'), z)) for z in episodes._conn.execute(
            f"SELECT sache, kreis, bestaetigt_am FROM personen_kreis WHERE sache IN ({','.join('?' * len(u.sachen))})",
            u.sachen).fetchall()] if u.sachen else []
    vermerke = []
    buch = getattr(app.state, 'logbuch', None)
    if buch is not None and u.vermerke:
        with buch._lock:
            for zeit, art in buch._conn.execute(
                    f"SELECT zeit, art FROM ereignis WHERE id IN ({','.join('?' * len(u.vermerke))}) ORDER BY zeit",
                    u.vermerke).fetchall():
                vermerke.append({'zeit': datetime.fromtimestamp(zeit, timezone.utc).isoformat(timespec='seconds'),
                                 'art': art})
    cloud = []
    try:
        from . import nach_draussen
        cloud = nach_draussen.protokoll(buch)
    except Exception:  # noqa: BLE001
        cloud = []
    return {
        'format': FORMAT,
        'erstellt': jetzt.astimezone().isoformat(timespec='seconds'),
        'person': {'name': u.anzeige, 'schreibweisen': u.namen, 'adressen': u.adressen,
                   'letzter_kontakt': _datum(mensch.letzter_kontakt),
                   # Nur Themen in Worten; technische Marken („mail:message:…“) sind keine Auskunft.
                   'themen': [t for t in mensch.themen if ':' not in t],
                   'kreis': kreis},
        'zahlen': u.zahlen(),
        'wissen': wissen,
        'vorschlaege': vorschlaege,
        'aufgaben': aufgaben,
        'projekte': u.projekte,
        'zusammenfuehrungen': zusammen,
        'quellen': quellen,
        'vermerke': vermerke,
        'cloud': {'satz': ('Kingfisher hält zu jeder Anfrage an einen Cloudanbieter fest, wann, wohin und wofür, '
                           'aber nicht welchen Inhalt. Ob eine davon Quellen dieser Person enthielt, lässt sich daraus '
                           'nicht sagen.'),
                  'anfragen': cloud},
        'hinweis': ('Aus Quellen, an denen auch andere beteiligt sind, stehen hier nur die Zeilen, die diese Person '
                    'nennen; fremde Adressen sind unkenntlich, weitere Beteiligte nur gezählt.'),
    }


_STAND = {'pending': 'offen', 'accepted': 'angenommen', 'rejected': 'abgelehnt', 'superseded': 'ersetzt',
          'active': 'gilt', 'retracted': 'widerrufen', 'expired': 'abgelaufen', 'open': 'offen', 'done': 'erledigt',
          'dropped': 'verworfen'}
_VERMERK = {'akte_neu': 'Akte angelegt', 'akte_aktualisiert': 'Akte ergänzt', 'vorschlag_angenommen': 'Vorschlag angenommen',
            'vorschlag_abgelehnt': 'Vorschlag abgelehnt', 'vorschlag_erzeugt': 'Vorschlag entstanden',
            'aufgabe_post': 'Aufgabe nach Post', 'akte_vorschlag': 'Neue Akte vorgeschlagen', 'lint': 'Befund'}
_ROLLE = {'von': 'von ihr', 'an': 'an sie', 'cc': 'in Kopie', 'bcc': 'in Blindkopie', 'beteiligt': 'beteiligt'}
_ART = {'task': 'Aufgabe', 'knowledge': 'Wissen', 'assertion': 'Angabe', 'memory': 'Wissen'}


def _wort(wert: Any, woerter: dict[str, str]) -> str:
    return woerter.get(str(wert), str(wert or ''))


def _zeit(wert: Any) -> str:
    """„29.09.2026, 06:30“ aus einer ISO-Zeit; sonst der Wert."""
    try:
        zeit = datetime.fromisoformat(str(wert))
    except (TypeError, ValueError):
        return str(wert or '')
    if zeit.tzinfo is not None:
        zeit = zeit.astimezone()
    return zeit.strftime('%d.%m.%Y, %H:%M')


def _h(text: Any) -> str:
    return html.escape(str(text if text is not None else ''), quote=True)


def als_html(daten: dict[str, Any]) -> str:
    """Die Auskunft für Menschen: eine Seite ohne Skript und ohne Verweise nach draußen, druckbar."""
    p = daten['person']
    teile = [
        '<!doctype html><html lang="de"><head><meta charset="utf-8">',
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">",
        f'<title>Auskunft: {_h(p["name"])}</title>',
        '<style>body{font:16px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1f2328}'
        'h1{font-size:1.6rem}h2{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #ccd}'
        'blockquote{margin:.3rem 0 .3rem 1rem;padding-left:.6rem;border-left:3px solid #ccd;white-space:pre-wrap}'
        'small{color:#555}li{margin:.35rem 0}</style></head><body>',
        f'<h1>Was Kingfisher über {_h(p["name"])} weiß</h1>',
        f'<p><small>Erstellt am {_h(_zeit(daten["erstellt"]))}. Diese Datei hat Kingfisher auf diesem Rechner erstellt; '
        'sie wurde nirgendwohin gesendet.</small></p>',
        '<h2>Person</h2><ul>',
        f'<li>Name: {_h(p["name"])}</li>',
    ]
    if p['schreibweisen'][1:]:
        teile.append(f'<li>Weitere Schreibweisen: {_h(", ".join(p["schreibweisen"][1:]))}</li>')
    if p['adressen']:
        teile.append(f'<li>Adressen: {_h(", ".join(p["adressen"]))}</li>')
    if p.get('letzter_kontakt'):
        teile.append(f'<li>Letzter Kontakt: {_h(_zeit(p["letzter_kontakt"]))}</li>')
    if p.get('themen'):
        teile.append(f'<li>Themen: {_h(", ".join(p["themen"]))}</li>')
    for k in p.get('kreis') or []:
        teile.append(f'<li>Kreis: {_h(k.get("kreis"))}</li>')
    teile.append('</ul>')

    def liste(titel: str, eintraege: list[str], leer: str) -> None:
        teile.append(f'<h2>{_h(titel)}</h2>')
        teile.append('<ul>' + ''.join(f'<li>{e}</li>' for e in eintraege) + '</ul>' if eintraege
                     else f'<p>{_h(leer)}</p>')

    liste('Bestätigtes Wissen', [f'{_h(w["aussage"])} <small>({_h(_wort(w["stand"], _STAND))}, seit {_h(_zeit(w["seit"]))})</small>'
                                 for w in daten['wissen']], 'Kein bestätigtes Wissen.')
    liste('Vorschläge', [f'{_h(v["vorschlag"])} <small>({_h(_wort(v["art"], _ART))}, {_h(_wort(v["stand"], _STAND))})</small>'
                         for v in daten['vorschlaege']], 'Keine Vorschläge.')
    liste('Aufgaben', [f'{_h(a["titel"])} <small>({_h(_wort(a["stand"], _STAND))}'
                       + (f', wartet auf {_h(a["wartet_auf"])}' if a.get('wartet_auf') else '') + ')</small>'
                       for a in daten['aufgaben']], 'Keine Aufgaben.')
    liste('Projekte', [_h(n) for n in daten['projekte']], 'Kein Projekt.')
    liste('Zusammenführungen', [f'{_h(z["name"])} <small>({_h(", ".join(m or "" for m in z["mitglieder"]))})</small>'
                                for z in daten['zusammenfuehrungen']], 'Keine Zusammenführung.')
    quellen = []
    for q in daten['quellen']:
        kopf = (f'<strong>{_h(q["art"])}: {_h(q["titel"])}</strong> <small>{_h(_zeit(q["datum"]))} · '
                f'{_h(", ".join(_ROLLE.get(r, r) for r in q["rolle"]) or "genannt")}'
                + (f' · {q["weitere_beteiligte"]} weitere Beteiligte' if q['weitere_beteiligte'] else '')
                + '</small>')
        quellen.append(kopf + ''.join(f'<blockquote>{_h(z)}</blockquote>' for z in q['auszug']))
    liste('Quellen', quellen, 'Keine Quelle.')
    liste('Vermerke', [f'{_h(_zeit(v["zeit"]))} · {_h(_VERMERK.get(v["art"], v["art"]))}' for v in daten['vermerke']],
          'Keine Vermerke.')
    teile.append('<h2>Cloud</h2>')
    teile.append(f'<p>{_h(daten["cloud"]["satz"])}</p>')
    if daten['cloud']['anfragen']:
        teile.append('<ul>' + ''.join(f'<li>{_h(_zeit(a.get("zeit")))} · {_h(a.get("satz"))}</li>'
                                      for a in daten['cloud']['anfragen']) + '</ul>')
    else:
        teile.append('<p>In den letzten 30 Tagen ging keine Anfrage an einen Cloudanbieter.</p>')
    teile.append(f'<p><small>{_h(daten["hinweis"])}</small></p></body></html>')
    return ''.join(teile)


def dateiname(anzeige: str, jetzt: datetime | None = None) -> str:
    name = re.sub(r'[^\w-]+', '-', anzeige, flags=re.UNICODE).strip('-')[:60] or 'Person'
    return f'Auskunft-{name}-{(jetzt or datetime.now()).strftime("%Y-%m-%d")}.zip'


def auskunft_zip(daten: dict[str, Any]) -> bytes:
    """Ein ZIP mit `Auskunft.html` (für Menschen) und `Auskunft.json` (für Maschinen)."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, 'w', zipfile.ZIP_DEFLATED) as archiv:
        archiv.writestr('Auskunft.html', als_html(daten))
        archiv.writestr('Auskunft.json', json.dumps(daten, ensure_ascii=False, indent=2))
    return puffer.getvalue()


# -- Löschen -----------------------------------------------------------------------------------------------------


def _ohne_schutz(conn: Any, trigger: str, sql_trigger: str, anweisungen: list[tuple[str, tuple]]) -> int:
    """Löscht in einem Verlauf, der sonst nur anhängt: Schutz aus, löschen, Schutz wieder an, in einer Transaktion.

    Bricht etwas ab, gilt nichts davon (SQLite nimmt auch das Entfernen des Schutzes zurück).
    """
    geloescht = 0
    conn.execute('SAVEPOINT person_loeschen')
    try:
        conn.execute(f'DROP TRIGGER IF EXISTS {trigger}')
        for sql, werte in anweisungen:
            geloescht += conn.execute(sql, werte).rowcount
        conn.execute(sql_trigger)
        conn.execute('RELEASE person_loeschen')
    except Exception:
        conn.execute('ROLLBACK TO person_loeschen')
        conn.execute('RELEASE person_loeschen')
        raise
    return geloescht


def _in(werte: Iterable[Any]) -> tuple[str, tuple]:
    werte = tuple(werte)
    return ','.join('?' * len(werte)), werte


def _loeschen_wissen(app: Any, u: Umfang) -> None:
    claims = app.state.claims
    with claims._lock:
        conn = claims._conn
        with conn:
            if u.aussagen:
                platz, werte = _in(u.aussagen)
                conn.execute(f'DELETE FROM knowledge_changes WHERE claim_id IN ({platz})', werte)
                conn.execute(f'DELETE FROM knowledge_claims WHERE id IN ({platz})', werte)
            if u.zusammenfuehrungen:
                platz, werte = _in(u.zusammenfuehrungen)
                conn.execute(f'DELETE FROM person_merges WHERE id IN ({platz})', werte)
            if u.kennungen:
                platz, werte = _in(u.kennungen)
                conn.execute(f'DELETE FROM person_digest_cache WHERE person_ref IN ({platz})', werte)
            if u.entitaeten:
                platz, werte = _in(u.entitaeten)
                conn.execute(f'DELETE FROM entity_aliases WHERE entity_id IN ({platz})', werte)
                conn.execute(f"DELETE FROM entity_registry WHERE kind='person' AND id IN ({platz})", werte)
    proposals = app.state.proposals
    if u.vorschlaege:
        platz, werte = _in(u.vorschlaege)
        with proposals._lock:
            with proposals._conn:
                proposals._conn.execute(f'DELETE FROM proposals WHERE id IN ({platz})', werte)
    if u.nur_ihre:
        platz, werte = _in(u.nur_ihre)
        with proposals._lock:
            with proposals._conn:
                proposals._conn.execute(f'DELETE FROM task_analysis WHERE episode_id IN ({platz})', werte)
                proposals._conn.execute(f'DELETE FROM memory_analysis_jobs WHERE episode_id IN ({platz})', werte)


def _loeschen_aufgaben(app: Any, u: Umfang) -> None:
    from . import tasks as tasks_modul
    tasks = app.state.tasks
    with tasks._lock:
        conn = tasks._conn
        with conn:
            if u.aufgaben:
                platz, werte = _in(u.aufgaben)
                conn.execute(f'DELETE FROM tasks WHERE id IN ({platz})', werte)
                conn.execute(f'DELETE FROM task_requests WHERE task_id IN ({platz})', werte)
                conn.execute(f'DELETE FROM aufgaben_post_getrennt WHERE task_id IN ({platz})', werte)
                conn.execute(f'DELETE FROM aufgaben_auto_zurueck WHERE task_id IN ({platz})', werte)
                _ohne_schutz(conn, 'task_events_no_delete', tasks_modul._HISTORY_TRIGGERS['task_events_no_delete'],
                             [(f'DELETE FROM task_events WHERE task_id IN ({platz})', werte)])
            if u.vorschlaege:
                platz, werte = _in(u.vorschlaege)
                conn.execute(f'DELETE FROM aufgaben_auto_geprueft WHERE proposal_id IN ({platz})', werte)
                conn.execute(f'DELETE FROM aufgaben_auto_zurueck WHERE proposal_id IN ({platz})', werte)
            if u.nur_ihre:
                platz, werte = _in(u.nur_ihre)
                for tabelle in ('aufgaben_post_mails', 'aufgaben_post_getrennt', 'aufgaben_auto_zurueck'):
                    conn.execute(f'DELETE FROM {tabelle} WHERE episode_id IN ({platz})', werte)


def _loeschen_vermerke(app: Any, u: Umfang) -> None:
    from . import logbuch
    buch = getattr(app.state, 'logbuch', None)
    if buch is not None and u.vermerke:
        platz, werte = _in(u.vermerke)
        with buch._lock:
            with buch._conn:
                _ohne_schutz(buch._conn, 'ereignis_no_delete', logbuch._TRIGGER_DELETE.strip(),
                             [(f'DELETE FROM ereignis WHERE id IN ({platz})', werte)])
    befunde = getattr(app.state, 'lint_befunde', None)
    if befunde is not None and u.befunde:
        platz, werte = _in(u.befunde)
        with befunde._lock:
            with befunde._conn:
                befunde._conn.execute(f'DELETE FROM befund WHERE id IN ({platz})', werte)
    if u.nur_ihre:
        platz, werte = _in(u.nur_ihre)
        zuordnungen = getattr(app.state, 'zuordnungen', None)
        if zuordnungen is not None:
            with zuordnungen._lock:
                with zuordnungen._conn:
                    zuordnungen._conn.execute(f'DELETE FROM zuordnung WHERE episode_id IN ({platz})', werte)
        workspace = app.state.workspace
        with workspace._lock:
            with workspace._conn:
                workspace._conn.execute(f'DELETE FROM event_followups WHERE episode_id IN ({platz})', werte)


#: Tabellen der Quellenablage, die je Quelle etwas abgeleitet haben (für Quellen, die nur sie betreffen).
_JE_QUELLE = ('source_heads', 'working_memory_sources', 'mail_intake_analysis', 'memory_category_sources',
              'memory_category_topics', 'memory_category_corrections', 'memory_category_recheck',
              'memory_category_entities', 'sach_quellen', 'sach_bezuege', 'sach_nutzer',
              'projekt_automatik_zuordnungen')


def _loeschen_quellen(app: Any, u: Umfang, treffer: _Treffer) -> None:
    from . import source_index
    from .episodes import source_metadata_digest
    episodes = app.state.episodes
    conn = episodes._conn
    with episodes.transaction():
        for episode_id in u.zusammenfassungen:
            # Eine Zusammenfassung, die sie nennt: weg, die zusammengefassten Quellen kommen wieder hervor.
            try:
                episodes.delete_summary(episode_id)
            except Exception:  # noqa: BLE001 - schon weg
                pass
        if u.nur_ihre:
            platz, werte = _in(u.nur_ihre)
            conn.execute(f'DELETE FROM working_memory_terms WHERE item IN '
                         f'(SELECT id FROM working_memory_items WHERE episode_id IN ({platz}))', werte)
            conn.execute(f'DELETE FROM working_memory_items WHERE episode_id IN ({platz})', werte)
            for tabelle in _JE_QUELLE:
                conn.execute(f'DELETE FROM {tabelle} WHERE episode_id IN ({platz})', werte)
            # Die Aufnahme merkt sich die Mail als ausgelassen (wie Werbung), nicht als Fehler.
            conn.execute(f"UPDATE mail_intake_items SET status='filtered:gesperrt', episode_id=NULL "
                         f"WHERE episode_id IN ({platz})", werte)
            conn.execute(f'DELETE FROM episodes WHERE id IN ({platz})', werte)
            for episode_id in u.nur_ihre:
                source_index.entfernen(conn, episode_id)
        for episode_id in u.geteilte:
            episode = episodes.get(episode_id)
            episode.contacts = [c for c in episode.contacts if not treffer.kontakt(c)]
            episode.participants = [t for t in episode.participants if not treffer.text(t)]
            dokument = episode.to_dict()
            zeile = conn.execute('SELECT source_key FROM episodes WHERE id=?', (episode_id,)).fetchone()
            conn.execute('UPDATE episodes SET document=?, metadata_digest=?, support_generation=support_generation+1 '
                         'WHERE id=?', (json.dumps(dokument, ensure_ascii=False),
                                        source_metadata_digest(dokument) if zeile[0] else '', episode_id))
            source_index.synchronisieren(conn, episode_id, neu=True)
        if u.sachen:
            platz, werte = _in(u.sachen)
            for tabelle in ('sach_bezuege', 'sach_nutzer', 'akten_cache', 'lagen', 'personen_kreis', 'akten_arten',
                            'akten_vorschlag_entscheidungen'):
                conn.execute(f'DELETE FROM {tabelle} WHERE sache IN ({platz})', werte)
            conn.execute(f'DELETE FROM akten_entscheidungen WHERE ' +
                         ' OR '.join('ziel LIKE ?' for _ in u.sachen), tuple(s + '%' for s in u.sachen))
        # Zusammenstellungen anderer Akten können ihre Quellen zitiert haben: neu rechnen.
        conn.execute('DELETE FROM akten_cache')
        if u.nur_ihre or u.geteilte:
            muster = [f'%{e}%' for e in [*u.nur_ihre, *u.adressen]]
            conn.execute('DELETE FROM lagen WHERE ' + ' OR '.join('daten LIKE ?' for _ in muster), tuple(muster))


def _zwischenspeicher_leeren(app: Any) -> None:
    for name in ('akten_lesungen', 'verzeichnis_zwischen'):
        speicher = getattr(app.state, name, None)
        if speicher is not None:
            speicher.leeren()
    episodes = app.state.episodes
    for name in ('_teilnehmer_zwischen',):
        speicher = getattr(episodes, name, None)
        if speicher is not None:
            speicher.leeren()
    alle = getattr(episodes, '_teilnehmer_alle', None)
    if isinstance(alle, dict):
        alle.clear()
    bezuege = getattr(app.state, 'bezuege', None)
    zwischen = getattr(bezuege, 'zwischen', None)
    if zwischen is not None:
        zwischen.leeren()


def _vektoren_vergessen(app: Any) -> int:
    """Die Bedeutungssuche: Einträge zu gelöschten Quellen sofort aus dem abgeleiteten Zwischenspeicher nehmen.

    Die Suche liefert sie ohnehin nicht mehr (jede Fundstelle wird gegen die Quelle geprüft); hier verschwinden auch
    die Vektoren selbst, soweit der Speicher offen ist. Sonst räumt ihn der nächste Lauf der Bedeutungssuche auf.
    """
    dienst = getattr(app.state, 'semantic_search', None)
    index = getattr(dienst, '_index', None)
    if index is None:
        return 0
    weg = 0
    try:
        with dienst._lock:
            while True:
                n = index.prune(64)
                weg += n
                if n < 64:
                    break
    except Exception:  # noqa: BLE001 - abgeleitet; der nächste Lauf räumt auf
        return weg
    return weg


def loeschen(app: Any, angabe: str) -> dict[str, Any]:
    """Löscht alles zu der Person und legt den Sperrvermerk an. Gibt die Zahlen und den Vermerk zurück."""
    u, mensch = umfang(app, angabe)
    treffer = _Treffer(u.adressen, u.namen if not u.adressen else [], _fremde_namen(app, set(u.adressen)))
    if not u.adressen:
        treffer.namen = {name_schluessel(n) for n in u.namen}
    from .person_sperre import fuer
    # Zuerst die Sperre: Was während des Löschens hereinkommt, kommt schon ohne sie herein.
    sperre = fuer(app.state.episodes).eintragen(u.anzeige, u.adressen, u.namen if not u.adressen else u.namen)
    _loeschen_wissen(app, u)
    _loeschen_aufgaben(app, u)
    _loeschen_vermerke(app, u)
    # Die Quellen zuletzt: Bricht vorher etwas ab, ist die Person noch auffindbar und das Löschen lässt sich
    # wiederholen.
    _loeschen_quellen(app, u, treffer)
    _zwischenspeicher_leeren(app)
    vektoren = _vektoren_vergessen(app)
    zahlen = u.zahlen()
    audit = getattr(app.state, 'audit', None)
    if audit is not None:
        try:
            # Ohne Namen und Adresse: Das Protokoll hält fest, dass gelöscht wurde, nicht wen.
            audit.record('person_loeschen', 'write_local', 'auto', 'executed', {'sperre': sperre, **zahlen})
        except Exception:  # noqa: BLE001
            pass
    return {'name': u.anzeige, 'sperre': sperre, 'zahlen': zahlen, 'vektoren': vektoren}


def vorschau(app: Any, angabe: str) -> dict[str, Any]:
    """Für die Rückfrage: Name, was gelöscht wird und was bleibt (nur Zahlen)."""
    u, _ = umfang(app, angabe)
    return {'name': u.anzeige, 'zahlen': u.zahlen(), 'projekte': u.projekte}


__all__ = ['FORMAT', 'PersonNichtGefunden', 'Umfang', 'als_html', 'auskunft', 'auskunft_zip', 'dateiname',
           'loeschen', 'umfang', 'vorschau']

_ = asdict  # für Tests, die den Umfang als Wörterbuch ansehen
