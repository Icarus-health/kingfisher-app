"""Microsoft Graph, nur lesend: Outlook-Post, Kalender und Teams-Mitschriften als Quellen wie alle anderen.

Dieses Modul baut keine eigene Aufnahme. Es übersetzt Graph in die Formen, die Kingfisher schon kennt:

* `MicrosoftPost` sieht für die Mailaufnahme (`mail_intake.Intake`) aus wie ein IMAP-Postfach: `folders`,
  `inventory_page`, `message_in_folder`. Damit gelten dieselben Stände („300 von 1.200 gelesen“), dieselbe Drosselung
  und dieselbe Reihenfolge nach Nutzen (`hintergrund.py`: neue Post zuerst, der Rückstand von neu nach alt).
* `MicrosoftKalender` liefert `connectors.calendar.Event` wie der Google- und der CalDAV-Kalender.
* `Mitschriften` holt Teams-Mitschriften (VTT) der vergangenen Online-Besprechungen und legt sie über
  `transkript_eingang.aufnehmen` ab wie eine Datei aus dem Transkript-Ordner; Zuordnung zum Termin, Abschnitte,
  Vorschläge und Beleg laufen danach unverändert.

**Nur GET.** `GraphClient` kennt keine andere Methode, schickt das Token nur an die eingestellte Graph-Adresse
(`microsoft_anmeldung.graph_basis`, auch bei Folgeseiten aus `@odata.nextLink`) und reicht keine Antworttexte weiter.

**Die Nummern der Post.** Die Aufnahme rechnet mit IMAP-Nummern (UID, aufsteigend je Ordner); Graph hat Kennungen
(Text). `Postablage` (`microsoft.sqlite3`) vergibt deshalb je Ordner eine Nummer je Nachricht: aus der Eingangszeit
(Sekunden seit 1970, bei Gleichstand eins daneben), damit „neu nach alt“ stimmt, und eine Laufnummer (`seq`) in der
Reihenfolge, in der die Delta-Abfrage sie liefert. Die Laufnummer ist der Fortschritt, den die Aufnahme speichert:
Der Bestand bekommt 1, 2, 3 …, was nach der ersten vollständigen Abfrage neu kommt, `GRENZE + 1`, `GRENZE + 2` …
Geht die Ablage verloren, entsteht eine neue Generation, und die Aufnahme beginnt die Bestandsaufnahme neu
(wie bei einem geänderten UIDVALIDITY; schon aufgenommene Mails bleiben, Dubletten erkennt die Episodenschicht).
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import httpx

from .connectors.calendar import CalendarError, Event
from .connectors.mail import FULL_BODY_LIMIT, MailError, MailboxGenerationChanged, Message
from .microsoft_anmeldung import MicrosoftFehler, graph_basis

#: Laufnummern ab hier gehören zur neuen Post (nach der ersten vollständigen Delta-Abfrage).
GRENZE = 2_000_000_000
MAX_UID = 4294967295
#: Seiten der Delta-Abfrage je Bestandsaufnahme-Aufruf, und Nachrichten je Seite.
SEITEN_JE_AUFRUF = 3
SEITENGROESSE = 100
#: So oft fragt die Delta-Abfrage nach neuer Post höchstens (Sekunden), wenn der Bestand schon vollständig ist.
NEU_ABSTAND_S = 20.0
#: Größte Antwort, die gelesen wird (eine Mail, eine Mitschrift).
MAX_ANTWORT = 5 * 1024 * 1024
NETZ_ZEITGRENZE = 20.0

#: Die Ordner der Aufnahme: Name in der Aufnahme → bekannter Ordnername bei Graph.
ORDNER = {'INBOX': 'inbox', 'SentItems': 'sentitems'}
UMFANG = 'Posteingang und Gesendet; ohne Junk-E-Mail und Gelöschte Elemente.'

_FELDER = ('subject,from,sender,toRecipients,ccRecipients,bccRecipients,replyTo,receivedDateTime,sentDateTime,'
           'isRead,internetMessageId,internetMessageHeaders,body,bodyPreview,inferenceClassification')
_LISTENFELDER = 'subject,from,receivedDateTime,isRead,bodyPreview'


class GraphFehler(MicrosoftFehler):
    def __init__(self, grund: str, warten: float = 0.0) -> None:
        super().__init__(grund)
        self.warten = warten


def graph_get(url: str, *, headers: dict[str, str], params: dict[str, Any] | None = None) -> tuple[int, dict[str, str], bytes]:
    """Ein GET an Graph: (Status, Kopfzeilen, Inhalt). Es gibt keine zweite Methode."""
    try:
        with httpx.Client(timeout=NETZ_ZEITGRENZE, follow_redirects=False) as client:
            with client.stream('GET', url, headers=headers, params=params) as antwort:
                daten = b''
                for stueck in antwort.iter_bytes():
                    daten += stueck
                    if len(daten) > MAX_ANTWORT:
                        break
                return antwort.status_code, {k.lower(): v for k, v in antwort.headers.items()}, daten
    except httpx.HTTPError:
        raise GraphFehler('nicht_erreichbar') from None


class GraphClient:
    """Liest Graph mit dem Token eines Kontos. Nur GET, nur an die eingestellte Adresse, Fehler als Satz."""

    def __init__(self, token: Callable[[], str], request: Callable[..., tuple[int, dict[str, str], bytes]] = graph_get,
                 clock: Callable[[], float] = time.time) -> None:
        self.token, self.request, self.clock = token, request, clock
        self.ruhe_bis = 0.0

    def url(self, pfad: str) -> str:
        basis = graph_basis()
        ziel = pfad if pfad.startswith(('http://', 'https://')) else basis + '/' + pfad.lstrip('/')
        # Folgeseiten kommen als ganze Adresse von Graph; das Token geht trotzdem nur an die eingestellte Adresse.
        if not ziel.startswith(basis + '/'):
            raise GraphFehler('verboten')
        return ziel

    def holen(self, pfad: str, params: dict[str, Any] | None = None, *, kopf: dict[str, str] | None = None,
              roh: bool = False) -> Any:
        if self.clock() < self.ruhe_bis:
            raise GraphFehler('gedrosselt', self.ruhe_bis - self.clock())
        ziel = self.url(pfad)
        status, kopfzeilen, daten = self.request(ziel, headers={'Authorization': 'Bearer ' + self.token(),
                                                                 'Accept': 'application/json', **(kopf or {})},
                                                 params=params)
        if status in (429, 503, 504):
            try:
                warten = float(kopfzeilen.get('retry-after') or 60)
            except ValueError:
                warten = 60.0
            self.ruhe_bis = self.clock() + min(max(warten, 1.0), 3600.0)
            raise GraphFehler('gedrosselt', warten)
        if status == 401:
            raise GraphFehler('abgemeldet')
        if status == 403:
            raise GraphFehler('verboten')
        if status in (404, 410):
            raise GraphFehler('fehlt')
        if status != 200:
            raise GraphFehler('unbekannt')
        if roh:
            return daten
        try:
            inhalt = json.loads(daten.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise GraphFehler('unbekannt') from None
        if not isinstance(inhalt, dict):
            raise GraphFehler('unbekannt')
        return inhalt


def _zeit(wert: Any) -> datetime | None:
    if not isinstance(wert, str) or not wert:
        return None
    # Graph schreibt bis zu sieben Nachkommastellen; Python liest höchstens sechs. Ohne Zone gilt UTC.
    from .datumstext import iso_versuchen_utc
    return iso_versuchen_utc(re.sub(r'(\.\d{6})\d+', r'\1', wert))


def _adresse(eintrag: Any) -> tuple[str, str]:
    feld = eintrag.get('emailAddress') if isinstance(eintrag, dict) else None
    if not isinstance(feld, dict):
        return '', ''
    return str(feld.get('name') or '').strip(), str(feld.get('address') or '').strip()


def _absender(eintrag: Any) -> str:
    name, adresse = _adresse(eintrag)
    if name and adresse and name.casefold() != adresse.casefold():
        return f'{name} <{adresse}>'
    return adresse or name


# -- Die Ablage der Nummern ------------------------------------------------------------------------------------------

class Postablage:
    """Nummern je Graph-Kennung und der Stand der Delta-Abfrage je Konto und Ordner (`microsoft.sqlite3`)."""

    def __init__(self, pfad: Path) -> None:
        self.pfad = Path(pfad)
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.pfad), check_same_thread=False, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        with self.lock:
            self.db.execute('CREATE TABLE IF NOT EXISTS meta(schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL)')
            self.db.execute('''CREATE TABLE IF NOT EXISTS ordner(konto TEXT NOT NULL, ordner TEXT NOT NULL, link TEXT,
                fertig INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(konto, ordner))''')
            self.db.execute('''CREATE TABLE IF NOT EXISTS post(konto TEXT NOT NULL, ordner TEXT NOT NULL,
                seq INTEGER NOT NULL, uid INTEGER NOT NULL, graph_id TEXT NOT NULL, PRIMARY KEY(konto, ordner, seq),
                UNIQUE(konto, ordner, uid), UNIQUE(konto, ordner, graph_id))''')
            self.db.execute('''CREATE TABLE IF NOT EXISTS mitschrift(konto TEXT NOT NULL, termin TEXT NOT NULL,
                titel TEXT NOT NULL DEFAULT '', beginn TEXT, stand TEXT NOT NULL, satz TEXT NOT NULL DEFAULT '',
                versuche INTEGER NOT NULL DEFAULT 0, naechster REAL NOT NULL DEFAULT 0, episoden TEXT NOT NULL DEFAULT '[]',
                geaendert REAL NOT NULL DEFAULT 0, PRIMARY KEY(konto, termin))''')
            if self.db.execute("SELECT 1 FROM meta WHERE schluessel='generation'").fetchone() is None:
                self.db.execute("INSERT INTO meta VALUES('generation', ?)", (str(random.randint(1, 2**31 - 1)),))

    def generation(self) -> str:
        with self.lock:
            return self.db.execute("SELECT wert FROM meta WHERE schluessel='generation'").fetchone()[0]

    def ordnerstand(self, konto: str, ordner: str) -> tuple[str | None, bool]:
        with self.lock:
            zeile = self.db.execute('SELECT link, fertig FROM ordner WHERE konto=? AND ordner=?', (konto, ordner)).fetchone()
        return (zeile[0], bool(zeile[1])) if zeile else (None, False)

    def ordner_merken(self, konto: str, ordner: str, link: str | None, fertig: bool) -> None:
        with self.lock:
            self.db.execute('INSERT INTO ordner(konto, ordner, link, fertig) VALUES(?,?,?,?) ON CONFLICT(konto, ordner) '
                            'DO UPDATE SET link=excluded.link, fertig=excluded.fertig', (konto, ordner, link, int(fertig)))

    def zuordnen(self, konto: str, ordner: str, eintraege: list[tuple[str, datetime | None]], neu: bool) -> int:
        """Vergibt Nummer und Laufnummer für unbekannte Kennungen; gibt die Zahl der neuen zurück."""
        gezaehlt = 0
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                for graph_id, eingang in eintraege:
                    if self.db.execute('SELECT 1 FROM post WHERE konto=? AND ordner=? AND graph_id=?',
                                       (konto, ordner, graph_id)).fetchone():
                        continue
                    bereich = 'seq >= ?' if neu else 'seq < ?'
                    hoechste = self.db.execute(f'SELECT MAX(seq) FROM post WHERE konto=? AND ordner=? AND {bereich}',
                                               (konto, ordner, GRENZE)).fetchone()[0]
                    seq = (hoechste or (GRENZE if neu else 0)) + 1
                    uid = min(max(int((eingang or datetime.now(timezone.utc)).timestamp()), 1), MAX_UID)
                    schritt = 1 if neu else -1
                    while self.db.execute('SELECT 1 FROM post WHERE konto=? AND ordner=? AND uid=?',
                                          (konto, ordner, uid)).fetchone():
                        uid += schritt
                        if uid < 1:
                            uid, schritt = int(time.time()), 1
                    self.db.execute('INSERT INTO post VALUES(?,?,?,?,?)', (konto, ordner, seq, uid, graph_id))
                    gezaehlt += 1
                self.db.execute('COMMIT')
            except Exception:
                self.db.execute('ROLLBACK')
                raise
        return gezaehlt

    def seite(self, konto: str, ordner: str, nach: int, bis: int, anzahl: int) -> list[tuple[int, int]]:
        with self.lock:
            return self.db.execute('SELECT seq, uid FROM post WHERE konto=? AND ordner=? AND seq>? AND seq<? '
                                   'ORDER BY seq LIMIT ?', (konto, ordner, nach, bis, anzahl)).fetchall()

    def kennung(self, konto: str, ordner: str, uid: int) -> str | None:
        with self.lock:
            zeile = self.db.execute('SELECT graph_id FROM post WHERE konto=? AND ordner=? AND uid=?',
                                    (konto, ordner, uid)).fetchone()
        return zeile[0] if zeile else None

    def vergessen(self, konto: str) -> None:
        with self.lock:
            for tabelle in ('ordner', 'post', 'mitschrift'):
                self.db.execute(f'DELETE FROM {tabelle} WHERE konto=?', (konto,))

    # Mitschriften
    def mitschrift(self, konto: str, termin: str) -> dict[str, Any] | None:
        with self.lock:
            self.db.row_factory = sqlite3.Row
            try:
                zeile = self.db.execute('SELECT * FROM mitschrift WHERE konto=? AND termin=?', (konto, termin)).fetchone()
            finally:
                self.db.row_factory = None
        return dict(zeile) if zeile else None

    def mitschrift_merken(self, konto: str, termin: str, **werte: Any) -> None:
        alt = self.mitschrift(konto, termin) or {'titel': '', 'beginn': None, 'stand': 'offen', 'satz': '',
                                                'versuche': 0, 'naechster': 0.0, 'episoden': '[]'}
        alt.update(werte, geaendert=time.time())
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO mitschrift(konto, termin, titel, beginn, stand, satz, versuche, '
                            'naechster, episoden, geaendert) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (konto, termin, alt['titel'], alt['beginn'], alt['stand'], alt['satz'], alt['versuche'],
                             alt['naechster'], alt['episoden'], alt['geaendert']))

    def mitschriften(self, konto: str, anzahl: int = 20) -> list[dict[str, Any]]:
        with self.lock:
            self.db.row_factory = sqlite3.Row
            try:
                zeilen = self.db.execute('SELECT * FROM mitschrift WHERE konto=? ORDER BY beginn DESC LIMIT ?',
                                         (konto, anzahl)).fetchall()
            finally:
                self.db.row_factory = None
        return [dict(z) for z in zeilen]


# -- Post ------------------------------------------------------------------------------------------------------------

class MicrosoftPost:
    """Ein Outlook-Postfach über Graph, mit der Schnittstelle des IMAP-Postfachs für Aufnahme und Anzeige."""

    umfang = UMFANG

    def __init__(self, adresse: str, client: GraphClient, ablage: Postablage, clock: Callable[[], float] = time.time):
        self.adresse = adresse.strip()
        self.konto = self.adresse.casefold()
        self.client, self.ablage, self.clock = client, ablage, clock
        self._zuletzt: dict[str, float] = {}
        self._lock = threading.Lock()

    # Für die Aufnahme ------------------------------------------------------------------------------------------------

    def folders(self) -> list[dict[str, Any]]:
        # Eine Anfrage, damit „Mails einlesen“ sofort den Grund sagt, wenn die Anmeldung nicht mehr gilt.
        self.client.holen('me/mailFolders/inbox', {'$select': 'id'})
        return [{'name': name, 'historical': True, 'flags': []} for name in ORDNER]

    def pruefe_anmeldung(self, timeout: float = 8.0) -> None:
        self.client.holen('me', {'$select': 'id'})

    def _fortschreiben(self, ordner: str) -> None:
        """Holt bis zu `SEITEN_JE_AUFRUF` Seiten der Delta-Abfrage und vergibt Nummern für Unbekannte."""
        if ordner not in ORDNER:
            raise MailError('Diesen Mailordner liest Kingfisher bei Microsoft nicht.')
        with self._lock:
            link, fertig = self.ablage.ordnerstand(self.konto, ordner)
            if fertig and self.clock() - self._zuletzt.get(ordner, 0.0) < NEU_ABSTAND_S:
                return
            self._zuletzt[ordner] = self.clock()
            kopf = {'Prefer': f'odata.maxpagesize={SEITENGROESSE}, IdType="ImmutableId"'}
            for _ in range(SEITEN_JE_AUFRUF):
                if link:
                    params = None
                    ziel = link
                else:
                    ziel = f'me/mailFolders/{ORDNER[ordner]}/messages/delta'
                    params = {'$select': 'receivedDateTime'}
                try:
                    seite = self.client.holen(ziel, params, kopf=kopf)
                except GraphFehler as exc:
                    if exc.grund == 'fehlt' and link:
                        # Der Stand der Delta-Abfrage ist bei Microsoft verfallen: neu beginnen, Bekanntes bleibt.
                        self.ablage.ordner_merken(self.konto, ordner, None, fertig)
                        return
                    raise
                eintraege = [(str(e['id']), _zeit(e.get('receivedDateTime'))) for e in seite.get('value') or []
                             if isinstance(e, dict) and e.get('id') and '@removed' not in e]
                self.ablage.zuordnen(self.konto, ordner, eintraege, neu=fertig)
                weiter, delta = seite.get('@odata.nextLink'), seite.get('@odata.deltaLink')
                if weiter:
                    link = str(weiter)
                    self.ablage.ordner_merken(self.konto, ordner, link, fertig)
                    continue
                if delta:
                    link, fertig = str(delta), True
                self.ablage.ordner_merken(self.konto, ordner, link, fertig)
                return

    def inventory_page(self, folder: str, after_uid: int = 0, before_uid: int | None = None, limit: int = 100, *,
                       uidvalidity: str | None = None) -> dict[str, Any]:
        """Wie beim IMAP-Postfach; `after_uid`/`next_uid` sind hier Laufnummern (siehe Moduldoku)."""
        generation = self.ablage.generation()
        if uidvalidity is not None and uidvalidity != generation:
            raise MailboxGenerationChanged('Die Postfachgeneration ist veraltet. Bitte die Bestandsaufnahme neu starten.')
        if type(after_uid) is not int or not 0 <= after_uid <= MAX_UID or not 1 <= limit <= 1000:
            raise ValueError('Ungültiger Mail-Fortschritt.')
        self._fortschreiben(folder)
        _, fertig = self.ablage.ordnerstand(self.konto, folder)
        neu = after_uid >= GRENZE
        zeilen = self.ablage.seite(self.konto, folder, after_uid, MAX_UID + 1 if neu else GRENZE, limit)
        weiter = zeilen[-1][0] if zeilen else after_uid
        rest = self.ablage.seite(self.konto, folder, weiter, MAX_UID + 1 if neu else GRENZE, 1)
        return {'folder': folder, 'uidvalidity': generation, 'upper_uid': GRENZE, 'uids': sorted(u for _, u in zeilen),
                'next_uid': weiter, 'done': True if neu else bool(fertig and not rest)}

    def message_in_folder(self, folder: str, uid: str) -> Message:
        generation, _, nummer = str(uid).partition('.')
        if generation != self.ablage.generation():
            raise MailboxGenerationChanged('Die Nachrichtenkennung ist veraltet. Bitte den Posteingang neu laden.')
        if not nummer.isdigit():
            raise MailError('Die Nachrichtenkennung ist veraltet. Bitte den Posteingang neu laden.')
        kennung = self.ablage.kennung(self.konto, folder, int(nummer))
        if kennung is None:
            raise MailError(f'Nachricht {uid} nicht gefunden.')
        return self._nachricht(kennung, str(uid))

    def _nachricht(self, kennung: str, uid: str) -> Message:
        inhalt = self.client.holen(f'me/messages/{quote(kennung, safe="")}', {'$select': _FELDER},
                                   kopf={'Prefer': 'outlook.body-content-type="text", IdType="ImmutableId"'})
        koepfe = {str(k.get('name') or '').lower(): str(k.get('value') or '')
                  for k in inhalt.get('internetMessageHeaders') or [] if isinstance(k, dict)}
        text = str((inhalt.get('body') or {}).get('content') or '')
        empfaenger = []
        for feld, rolle in (('toRecipients', 'an'), ('ccRecipients', 'cc'), ('bccRecipients', 'bcc')):
            for eintrag in inhalt.get(feld) or []:
                name, adresse = _adresse(eintrag)
                if name or adresse:
                    empfaenger.append({'name': name, 'adresse': adresse.casefold(), 'rolle': rolle})
        antwort_an = next((_absender(e) for e in inhalt.get('replyTo') or [] if _adresse(e)[1]), '')
        return Message(
            uid=uid, subject=str(inhalt.get('subject') or ''), sender=_absender(inhalt.get('from') or inhalt.get('sender')),
            date=_zeit(inhalt.get('receivedDateTime')) or _zeit(inhalt.get('sentDateTime')),
            preview=' '.join(text.split())[:300], unread=not inhalt.get('isRead', False), body=text[:FULL_BODY_LIMIT],
            truncated=len(text) > FULL_BODY_LIMIT, message_id=str(inhalt.get('internetMessageId') or ''),
            reply_to=antwort_an,
            in_reply_to=koepfe.get('in-reply-to', '')[:16000],
            references=tuple(re.findall(r'<[^<>\s]{1,500}>', koepfe.get('references', '')[:16000])[:64]),
            spam_flag=any(koepfe.get(k, '').strip().lower().startswith(('yes', 'true')) for k in ('x-spam-flag', 'x-spam-status')),
            list_mail=bool(koepfe.get('list-id') or koepfe.get('list-unsubscribe')
                           or koepfe.get('precedence', '').lower() in ('bulk', 'list')),
            recipients=tuple(empfaenger), own_addresses=(self.konto,))

    # Für Anzeige und Prüfung -----------------------------------------------------------------------------------------

    def inbox(self, limit: int = 10, unread_only: bool = False) -> list[Message]:
        params: dict[str, Any] = {'$top': max(1, min(int(limit), 50)), '$orderby': 'receivedDateTime desc',
                                  '$select': _LISTENFELDER}
        if unread_only:
            params['$filter'] = 'isRead eq false'
        inhalt = self.client.holen('me/mailFolders/inbox/messages', params, kopf={'Prefer': 'IdType="ImmutableId"'})
        return [Message(uid=str(e['id']), subject=str(e.get('subject') or ''), sender=_absender(e.get('from')),
                        date=_zeit(e.get('receivedDateTime')), preview=' '.join(str(e.get('bodyPreview') or '').split())[:300],
                        unread=not e.get('isRead', False))
                for e in inhalt.get('value') or [] if isinstance(e, dict) and e.get('id')]

    def message(self, uid: str) -> Message:
        if re.fullmatch(r'\d+\.\d+', str(uid)):
            return self.message_in_folder('INBOX', uid)
        return self._nachricht(str(uid), str(uid))

    def pending_uids(self, after: str | None = None, limit: int = 50) -> list[str]:
        raise MailError('Bei einem Microsoft-Konto liest Kingfisher die Post über „Mails einlesen“.')

    def sender_label(self, account_id: str = '') -> str:
        return self.adresse


# -- Kalender --------------------------------------------------------------------------------------------------------

_TERMINFELDER = ('subject,start,end,isAllDay,isCancelled,location,attendees,organizer,bodyPreview,iCalUId,'
                 'isOnlineMeeting,onlineMeeting')


def termine(client: GraphClient, von: datetime, bis: datetime, seiten: int = 20) -> list[dict[str, Any]]:
    """Die Rohdaten der Termine zwischen `von` und `bis` aus `/me/calendarView` (Wiederholungen aufgelöst)."""
    params: dict[str, Any] | None = {
        'startDateTime': von.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'endDateTime': bis.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        '$select': _TERMINFELDER, '$top': 100, '$orderby': 'start/dateTime'}
    ziel, ergebnis = 'me/calendarView', []
    for _ in range(seiten):
        seite = client.holen(ziel, params, kopf={'Prefer': 'outlook.timezone="UTC"'})
        ergebnis.extend(e for e in seite.get('value') or [] if isinstance(e, dict))
        weiter = seite.get('@odata.nextLink')
        if not weiter:
            return ergebnis
        ziel, params = str(weiter), None
    raise GraphFehler('unbekannt')


def _terminzeit(feld: Any) -> datetime | None:
    if not isinstance(feld, dict):
        return None
    moment = _zeit(feld.get('dateTime'))
    if moment is not None and (feld.get('timeZone') or 'UTC').upper() == 'UTC':
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


class MicrosoftKalender:
    """Der Outlook-Kalender (Standardkalender des Kontos) über `/me/calendarView`, nur lesend."""

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    def events(self, days: int = 7, at: datetime | None = None) -> list[Event]:
        at = at or datetime.now(timezone.utc)
        try:
            roh = termine(self.client, at, at + timedelta(days=days))
        except MicrosoftFehler as exc:
            raise CalendarError(exc.satz) from None
        ergebnis = []
        for e in roh:
            if e.get('isCancelled'):
                continue
            teilnehmer = []
            for eintrag in [*(e.get('attendees') or []), e.get('organizer')]:
                name, adresse = _adresse(eintrag)
                if adresse and not any(adresse.casefold() in t.casefold() for t in teilnehmer):
                    teilnehmer.append(f'{name} <{adresse}>' if name and name != adresse else adresse)
            ergebnis.append(Event(uid=str(e.get('iCalUId') or e.get('id') or ''), summary=str(e.get('subject') or '(ohne Titel)'),
                                  start=_terminzeit(e.get('start')), end=_terminzeit(e.get('end')),
                                  all_day=bool(e.get('isAllDay')),
                                  location=str((e.get('location') or {}).get('displayName') or ''),
                                  attendees=teilnehmer, notes=str(e.get('bodyPreview') or '')))
        return ergebnis


# -- Teams-Mitschriften ----------------------------------------------------------------------------------------------

#: So weit zurück sucht Kingfisher nach Besprechungen mit Mitschrift, und so viele behandelt ein Durchgang.
TAGE_ZURUECK = 14
JE_DURCHGANG = 10
#: Nach Ende einer Besprechung so lange auf eine Mitschrift warten; danach ist „keine“ endgültig.
WARTEN_NACH_ENDE_S = 2 * 24 * 3600
ERNEUT_S = 3600

SAETZE = {
    'aufgenommen': 'Mitschrift aufgenommen.',
    'keine': 'Für diese Besprechung gibt es bei Microsoft keine Mitschrift.',
    'noch_keine': 'Noch keine Mitschrift; Kingfisher sieht in einer Stunde wieder nach.',
    'nicht_erlaubt': 'Teams-Mitschriften gibt Microsoft erst frei, wenn die IT deiner Hochschule oder Firma zugestimmt hat.',
    'nicht_herausgegeben': 'Microsoft gibt die Mitschrift dieser Besprechung nicht heraus. Das geht meist nur bei '
                           'Besprechungen, die du selbst angesetzt hast.',
    'fehler': 'Die Mitschrift ließ sich gerade nicht holen; Kingfisher versucht es später noch einmal.',
}


def transkript_aus_vtt(vtt: str, titel: str, beginn: datetime | None, dateiname: str):
    """Eine Teams-Mitschrift (WebVTT mit `<v Name>`) als `transkript_eingang.Transkript`.

    Wie eine Datei aus dem Transkript-Ordner, mit einem Unterschied: Der Beginn der Mitschrift ist bekannt, und jede
    Wortmeldung behält ihre Uhrzeit („Anna Keller: [14:05] …“). So trägt jeder Beleg Sprecher und Zeit.
    """
    from .model import user_timezone
    from .transcript_import import parse_transcript
    from .transkript_eingang import Transkript, sprecher_und_text
    segmente = parse_transcript(vtt, 'vtt')
    zone = user_timezone() or timezone.utc
    zeilen: list[str] = []
    zuletzt = None
    for segment in segmente:
        inhalt = ' '.join(str(segment.get('text') or '').split())
        if not inhalt:
            continue
        sprecher = segment.get('speaker')
        if sprecher and sprecher == zuletzt and zeilen:
            zeilen[-1] += ' ' + inhalt
            continue
        marke = ''
        if beginn is not None and segment.get('start_ms') is not None:
            marke = '[' + (beginn + timedelta(milliseconds=int(segment['start_ms']))).astimezone(zone).strftime('%H:%M') + '] '
        zeilen.append(f'{sprecher}: {marke}{inhalt}' if sprecher else f'{marke}{inhalt}')
        zuletzt = sprecher
    if not zeilen:
        raise ValueError('Die Mitschrift ist leer.')
    text = '\n'.join(zeilen)
    echte, anonym, _ = sprecher_und_text(text)
    return Transkript(dateiname=dateiname, titel=titel or 'Teams-Besprechung', text=text, format='vtt',
                      sprecher=tuple(echte), anonyme_sprecher=anonym, beginn=beginn,
                      tag=beginn.astimezone(zone).date() if beginn else None, zeit_quelle='kopf' if beginn else '')


class Mitschriften:
    """Holt die Teams-Mitschriften vergangener Online-Besprechungen eines Kontos und legt sie als Quellen ab.

    `ablegen(transkript, source_key, ref)` legt eine Mitschrift ab und gibt die Episode zurück (Verdrahtung in
    `microsoft_routes`: Sperre, `transkript_eingang.aufnehmen`, Zuordnung zum Termin, Einordnung anstoßen).
    """

    def __init__(self, adresse: str, client: GraphClient, ablage: Postablage, ablegen: Callable[..., Any],
                 clock: Callable[[], float] = time.time) -> None:
        self.adresse, self.konto = adresse, adresse.strip().casefold()
        self.client, self.ablage, self.ablegen, self.clock = client, ablage, ablegen, clock

    def durchgang(self) -> dict[str, int]:
        jetzt = datetime.fromtimestamp(self.clock(), timezone.utc)
        zaehler = {'besprechungen': 0, 'aufgenommen': 0, 'ohne': 0}
        roh = termine(self.client, jetzt - timedelta(days=TAGE_ZURUECK), jetzt)
        kandidaten = []
        for e in roh:
            ende, url = _terminzeit(e.get('end')), str((e.get('onlineMeeting') or {}).get('joinUrl') or '')
            if not e.get('isOnlineMeeting') or not url or e.get('isCancelled') or ende is None or ende > jetzt:
                continue
            kandidaten.append((ende, e, url))
        kandidaten.sort(key=lambda k: k[0], reverse=True)
        for ende, e, url in kandidaten:
            termin = str(e.get('iCalUId') or e.get('id'))
            alt = self.ablage.mitschrift(self.konto, termin)
            if alt and (alt['stand'] in ('aufgenommen', 'keine', 'nicht_herausgegeben') or alt['naechster'] > self.clock()):
                continue
            if zaehler['besprechungen'] >= JE_DURCHGANG:
                break
            zaehler['besprechungen'] += 1
            beginn = _terminzeit(e.get('start'))
            titel = str(e.get('subject') or 'Teams-Besprechung')
            stand, neu = self._eine(termin, titel, beginn, ende, url, (alt or {}).get('versuche', 0))
            zaehler['aufgenommen' if stand == 'aufgenommen' else 'ohne'] += 1
            if stand == 'gedrosselt':
                break
        return zaehler

    def _eine(self, termin: str, titel: str, beginn: datetime | None, ende: datetime, url: str,
              versuche: int) -> tuple[str, int]:
        merken = dict(titel=titel[:300], beginn=beginn.isoformat() if beginn else None, versuche=versuche + 1)
        try:
            gefunden = self.client.holen('me/onlineMeetings',
                                         {'$filter': "JoinWebUrl eq '" + url.replace("'", "''") + "'"})
            besprechung = next((b for b in gefunden.get('value') or [] if isinstance(b, dict) and b.get('id')), None)
            if besprechung is None:
                self._stand(termin, 'nicht_herausgegeben', merken)
                return 'nicht_herausgegeben', 0
            mid = quote(str(besprechung['id']), safe='')
            liste = self.client.holen(f'me/onlineMeetings/{mid}/transcripts')
            eintraege = [t for t in liste.get('value') or [] if isinstance(t, dict) and t.get('id')]
            if not eintraege:
                spaet = self.clock() - ende.timestamp() > WARTEN_NACH_ENDE_S
                self._stand(termin, 'keine' if spaet else 'noch_keine', merken, warten=ERNEUT_S)
                return 'keine', 0
            episoden = []
            for eintrag in eintraege[:5]:
                tid = quote(str(eintrag['id']), safe='')
                daten = self.client.holen(f'me/onlineMeetings/{mid}/transcripts/{tid}/content',
                                          {'$format': 'text/vtt'}, kopf={'Accept': 'text/vtt'}, roh=True)
                start = _zeit(eintrag.get('createdDateTime')) or beginn
                transkript = transkript_aus_vtt(daten.decode('utf-8-sig', errors='replace'), titel, start,
                                                f'Teams: {titel}.vtt')
                episode = self.ablegen(transkript, f'microsoft:teams:{self.konto}:{eintrag["id"]}', f'teams:{titel}'[:200])
                episoden.append(episode.id)
            self._stand(termin, 'aufgenommen', merken, episoden=json.dumps(episoden))
            return 'aufgenommen', len(episoden)
        except GraphFehler as exc:
            if exc.grund == 'verboten':
                # Ohne Freigabe der IT oder fremde Besprechung: ehrlich, kein Fehler. Einmal am Tag neu versuchen.
                self._stand(termin, 'nicht_erlaubt', merken, warten=24 * 3600)
                return 'nicht_erlaubt', 0
            if exc.grund == 'fehlt':
                self._stand(termin, 'nicht_herausgegeben', merken)
                return 'nicht_herausgegeben', 0
            self._stand(termin, 'fehler', merken, warten=max(exc.warten, 15 * 60))
            return 'gedrosselt' if exc.grund == 'gedrosselt' else 'fehler', 0
        except ValueError:
            self._stand(termin, 'keine', merken)
            return 'keine', 0

    def _stand(self, termin: str, stand: str, merken: dict[str, Any], warten: float = 0.0, **mehr: Any) -> None:
        self.ablage.mitschrift_merken(self.konto, termin, stand=stand, satz=SAETZE.get(stand, ''),
                                      naechster=self.clock() + warten if warten else 0.0, **merken, **mehr)


__all__ = ['GRENZE', 'GraphClient', 'GraphFehler', 'MicrosoftKalender', 'MicrosoftPost', 'Mitschriften', 'ORDNER',
           'Postablage', 'SAETZE', 'UMFANG', 'graph_get', 'termine', 'transkript_aus_vtt']
