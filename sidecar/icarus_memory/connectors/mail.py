"""Mail über IMAP und SMTP.

Bewusst IMAP/SMTP statt Anbieter-APIs: Das funktioniert mit iCloud, Fastmail,
Mailbox.org, jedem eigenen Server und — mit App-Passwort — auch mit Gmail und
Outlook. Kein OAuth-Tanz, kein Anbieter, der die Schnittstelle abkündigt. Für
ein System, das Jahre laufen soll, ist das offene Protokoll die sicherere Wette.

**Sicherheitshinweis, der hier zentral ist:** Eine E-Mail ist der gefährlichste
Injection-Weg, den es gibt — jeder kann dir eine schreiben. Der Inhalt wird
deshalb ausnahmslos als fremd markiert und kontaminiert die Runde. Ein
Assistent, der Mails liest und danach ungefragt handelt, führt aus, was
Fremde ihm schreiben.
"""

from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
import re
import smtplib
import ssl
import hashlib
import threading
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from typing import Any, Callable

DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_PORT = 587

#: Wie viel vom Text eine einzeln geöffnete Nachricht mitbringt. Großzügig,
#: aber begrenzt — eine Mail mit einem eingebetteten Bild als Base64 hat
#: Megabyte, und die will niemand im Browser stehen haben.
FULL_BODY_LIMIT = 20_000
# Bound bytes received and parsed, including attachments. Text truncation alone
# cannot protect the background worker from a single very large MIME message.
MAX_MESSAGE_WIRE_BYTES = 2 * 1024 * 1024
# Die Liste braucht nur eine Vorschau. Ganze MIME-Anlagen verzögern sonst
# einen kleinen Posteingangsabruf bis über dessen feste Zeitgrenze hinaus.
MAX_INBOX_PREVIEW_BYTES = 64 * 1024
MAX_UID = 4294967295
MAX_INVENTORY_WINDOW = 1000
#: Namen, unter denen Mailserver ohne SPECIAL-USE-Attribut den Gesendet-Ordner führen (Vergleich ohne Groß/Klein,
#: der ganze Name samt Trennzeichen). Microsoft 365 heißt er `SentItems` (`microsoft_graph.ORDNER`).
GESENDET_NAMEN = frozenset({"sent", "sent items", "sent messages", "sent mail", "gesendet", "gesendete objekte",
                            "gesendete elemente", "inbox.sent", "inbox/sent", "sentitems"})


class MailError(Exception):
    pass


class MailboxGenerationChanged(MailError):
    """Der gespeicherte UID-Bestand gehört zu einer alten Postfachgeneration."""


class AnmeldungAbgelehnt(imaplib.IMAP4.error):
    """Der Server hat die Anmeldung abgelehnt (LOGIN oder XOAUTH2), nicht einen späteren Befehl.

    Unterklasse von `imaplib.IMAP4.error` mit dem Text des Servers, damit `mail_anmeldung.einordnen` sie wie bisher
    einordnet. Die Aufnahme erkennt daran, dass nur eine neue Anmeldung hilft (`mail_intake`, Grund `anmeldung`);
    ein BAD auf eine Suche ist dagegen kein Anmeldefehler.
    """


class AnmeldungRuht(AnmeldungAbgelehnt):
    """Ohne Verbindung abgewiesen: Dieselben Zugangsdaten hat der Server eben abgelehnt (`ANMELDUNG_RUHT_S`)."""


class AnmeldungWartet(OSError):
    """Ohne Verbindung: Der Server lehnte eben vorübergehend ab ([LIMIT], zu viele Anmeldungen); später erneut."""


#: Nach einer echten Ablehnung ruhen dieselben Zugangsdaten so lange für jede Verbindung (Sekunden). Jeder Versuch wäre
#: eine Anmeldung beim Anbieter; viele abgelehnte in Folge sperren dort das Konto.
ANMELDUNG_RUHT_S = 3600.0
#: Nach einer vorübergehenden Ablehnung erst so lange, dann jeweils doppelt so lange, höchstens `VORLAEUFIG_HOECHSTENS_S`.
VORLAEUFIG_ERST_S = 60.0
VORLAEUFIG_HOECHSTENS_S = 1800.0


def _ruhe_uhr() -> float:
    return time.time()


class _Anmelderuhe:
    """Kontoweit: Wann dieselben Zugangsdaten nach einer Ablehnung wieder an den Server dürfen (docs/47).

    Jede Verbindung meldet sich an: die Aufnahme (jeder Ordner), der Nachtrag der Beteiligten, der Posteingang auf
    Heute und unter „Nachrichten“. Erkannt werden die Zugangsdaten an Server, Port, Benutzer und einem Fingerabdruck
    des Passworts: Ein neues Passwort gilt sofort. Ausdrückliche Prüfungen (Verbinden, Neu anmelden) fragen immer den
    Server. Nur im Speicher; nach einem Neustart höchstens ein Versuch.
    """

    def __init__(self) -> None:
        self._sperre = threading.Lock()
        self._eintraege: dict[tuple[str, int, str, str], tuple[float, int, bool]] = {}

    def ruht(self, schluessel: tuple[str, int, str, str]) -> tuple[bool, bool]:
        """(ruht gerade, echte Ablehnung)."""
        with self._sperre:
            eintrag = self._eintraege.get(schluessel)
        if eintrag is None or _ruhe_uhr() >= eintrag[0]:
            return False, False
        return True, eintrag[2]

    def pruefen(self, schluessel: tuple[str, int, str, str]) -> None:
        ruht, echt = self.ruht(schluessel)
        if ruht and echt:
            raise AnmeldungRuht('[AUTHENTICATIONFAILED] Kingfisher meldet sich mit diesen Zugangsdaten vorerst nicht '
                                'erneut an.')
        if ruht:
            raise AnmeldungWartet('Das Postfach hat die Anmeldung eben vorübergehend abgelehnt; Kingfisher versucht es '
                                  'später erneut.')

    def abgelehnt(self, schluessel: tuple[str, int, str, str], echt: bool) -> None:
        with self._sperre:
            alt = self._eintraege.get(schluessel)
            folge = (alt[1] if alt is not None and alt[2] == echt else 0) + 1
            dauer = ANMELDUNG_RUHT_S if echt else min(VORLAEUFIG_HOECHSTENS_S, VORLAEUFIG_ERST_S * 2 ** (folge - 1))
            self._eintraege[schluessel] = (_ruhe_uhr() + dauer, folge, echt)

    def gelungen(self, schluessel: tuple[str, int, str, str]) -> None:
        self._vergessen(lambda k: k[:3] == schluessel[:3])

    def vergessen(self, benutzer: str) -> None:
        """Nach einer neuen Anmeldung (auch Google, Microsoft): sofort wieder versuchen."""
        benutzer = (benutzer or '').casefold()
        self._vergessen(lambda k: k[2] == benutzer)

    def _vergessen(self, passt: Callable[[tuple[str, int, str, str]], bool]) -> None:
        with self._sperre:
            for schluessel in [k for k in self._eintraege if passt(k)]:
                del self._eintraege[schluessel]


ANMELDERUHE = _Anmelderuhe()


@dataclass
class MailConfig:
    imap_host: str
    username: str
    password: str
    smtp_host: str = ""
    imap_port: int = DEFAULT_IMAP_PORT
    smtp_port: int = DEFAULT_SMTP_PORT
    from_address: str = ""
    access_token: Callable[[], str] | None = None

    @property
    def sender(self) -> str:
        return self.from_address or self.username

    @classmethod
    def from_env(cls, env: dict[str, str]) -> MailConfig | None:
        host = env.get("ICARUS_IMAP_HOST")
        user = env.get("ICARUS_MAIL_USER")
        password = env.get("ICARUS_MAIL_PASSWORD")
        if not (host and user and password):
            return None
        return cls(
            imap_host=host,
            username=user,
            password=password,
            smtp_host=env.get("ICARUS_SMTP_HOST", ""),
            imap_port=int(env.get("ICARUS_IMAP_PORT", DEFAULT_IMAP_PORT)),
            smtp_port=int(env.get("ICARUS_SMTP_PORT", DEFAULT_SMTP_PORT)),
            from_address=env.get("ICARUS_MAIL_FROM", ""),
        )


@dataclass
class Message:
    uid: str
    subject: str
    sender: str
    date: datetime | None
    preview: str
    unread: bool

    body: str = ""
    """Der volle Text — nur beim Einzelabruf gefüllt.

    Die Liste trägt ihn nicht: Zwanzig ganze Mails sind ein Vielfaches der
    Datenmenge, und sie stehen ohnehin zusammengefaltet da.
    """

    message_id: str = ""
    """Für `In-Reply-To`. Ohne den Kopf hängt eine Antwort nicht am Verlauf,
    sondern erscheint beim Empfänger als neue Nachricht."""

    in_reply_to: str = ""
    references: tuple[str, ...] = ()

    reply_to: str = ""
    """`Reply-To`, wo gesetzt. Sonst ist der Absender gemeint."""

    account_id: str = ""
    account_label: str = ""
    truncated: bool = False
    spam_flag: bool = False
    list_mail: bool = False
    provider_id: str = ""
    """Optionale ordnerübergreifende Anbieterkennung, etwa Gmail X-GM-MSGID."""

    recipients: tuple[dict[str, Any], ...] = ()
    """Empfänger aus `To`, `Cc` und `Bcc` mit Rolle (`an`/`cc`/`bcc`), Name und
    Adresse; siehe `kontakte.py`. Nur beim Einzelabruf gefüllt. `Bcc` liefert der
    Server nur in der eigenen Kopie unter „Gesendet“."""

    own_addresses: tuple[str, ...] = ()
    """Adressen des Kontos, über das die Mail geholt wurde (Benutzername und
    Absenderadresse). Damit erkennt die Aufnahme „ich“, ohne nachzufragen."""

    entwurf: bool = False
    """Flag `\\Draft`: ein nie abgeschickter Entwurf (Gmail führt ihn im Gesamtbestand).
    Nichts, was geschah; die Aufnahme überspringt ihn."""

    anhaenge: tuple[Any, ...] = ()
    """Gelesene Anhänge (PDF, Foto einer Rechnung) als `anhaenge.Anhang`; nur beim
    Abruf für die Aufnahme gefüllt (`message_mit_anhaengen`), nie beim Ansehen."""
    anhang_bericht: dict[str, Any] | None = None
    """None means not inspected, never proof that the message has no attachments."""

    def answer_address(self) -> str:
        """An wen eine Antwort geht. `Reply-To` gewinnt — dafür steht er da."""
        return self.reply_to or self.sender

    def to_dict(self) -> dict[str, Any]:
        result = {
            "uid": self.uid,
            "subject": self.subject,
            "from": self.sender,
            "date": self.date.astimezone().isoformat() if self.date else None,
            "preview": self.preview,
            "unread": self.unread,
            "body": self.body,
            "message_id": self.message_id,
            "answer_to": self.answer_address(),
            "truncated": self.truncated,
        }
        if self.account_id:
            result["account_id"] = self.account_id
            result["account_label"] = self.account_label
        if self.provider_id:
            result["provider_id"] = self.provider_id
        return result


def _empfaenger(parsed: Any) -> tuple[dict[str, Any], ...]:
    """`To`, `Cc` und `Bcc` einer geparsten Mail als Beteiligte mit Rolle.

    Die Kopfzeilen werden **vor** dem Dekodieren getrennt: Ein kodierter Name
    „=?utf-8?…?=“ darf ein Komma enthalten („Keller, Anna“), ohne die Liste
    zu zerreißen. Erst die einzelnen Namen werden entschlüsselt.
    """
    from email.utils import getaddresses

    ergebnis: list[dict[str, Any]] = []
    for kopf, rolle in (("To", "an"), ("Cc", "cc"), ("Bcc", "bcc")):
        for name, adresse in getaddresses([str(w) for w in parsed.get_all(kopf, [])]):
            adresse = adresse.strip().casefold()
            name = _decode(name)
            if adresse or name:
                ergebnis.append({"name": name, "adresse": adresse, "rolle": rolle})
    return tuple(ergebnis)


def _decode(raw: str | None) -> str:
    """Entschlüsselt MIME-kodierte Kopfzeilen (=?utf-8?B?...?=)."""
    if not raw:
        return ""
    parts = []
    for text, charset in email.header.decode_header(raw):
        if isinstance(text, bytes):
            parts.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(text)
    return "".join(parts).strip()


class _MailText(HTMLParser):
    """HTML nur als Text lesen; keine Bilder, Skripte oder Netzwerkaufrufe."""
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in ("script", "style"):
            self.hidden += 1
        if not self.hidden and tag in ("p", "div", "br", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag in ("p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _body(message: email.message.Message, limit: int = 500) -> str:
    """Zieht den Textkörper heraus, bevorzugt text/plain."""
    parts = [part for part in message.walk() if not part.get_filename()]
    part = next((part for part in parts if part.get_content_type() == "text/plain"), None)
    if part is None:
        part = next((part for part in parts if part.get_content_type() == "text/html"), None)
    if part is None:
        return ""
    payload = part.get_payload(decode=True) or b""
    try:
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError:
        text = payload.decode("utf-8", errors="replace")
    if part.get_content_type() == "text/html":
        parser = _MailText()
        parser.feed(text)
        text = "".join(parser.parts).strip()
    return text[:limit]


def _mailbox_validity(imap: Any) -> str:
    value = _mailbox_number(imap, "UIDVALIDITY", MAX_UID)
    return str(value)


def _mailbox_number(imap: Any, name: str, maximum: int) -> int:
    response = imap.response(name)[1]
    raw = response[0] if response and response[0] else b""
    try:
        value = raw.decode("ascii") if isinstance(raw, bytes) else str(raw)
    except UnicodeDecodeError as exc:
        raise MailError("Das Postfach liefert keine stabile Nachrichtenkennung.") from exc
    if not value.isascii() or not value.isdigit() or not 0 < int(value) <= maximum:
        raise MailError("Das Postfach liefert keine stabile Nachrichtenkennung.")
    return int(value)


def ist_gesendet_ordner(name: str, attributes: Any = ()) -> bool:
    """Ob dieser Ordner die gesendeten Mails hält: SPECIAL-USE `\\Sent` (RFC 6154), sonst ein üblicher Name."""
    if any(str(value).lower() == "\\sent" for value in attributes or ()):
        return True
    return str(name or "").strip().casefold() in GESENDET_NAMEN


def _folder_argument(folder: str) -> str:
    if not isinstance(folder, str) or not folder or any(ord(char) < 32 or ord(char) == 127 for char in folder):
        raise ValueError("Ungültiger Mailordner.")
    # imaplib does not quote mailbox arguments itself. Keep INBOX compatible
    # with the existing API and quote every discovered folder without guessing
    # whether a space or other IMAP grammar character needs escaping.
    if folder.upper() == "INBOX":
        return "INBOX"
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _list_string(value: str) -> tuple[str | None, str]:
    value = value.lstrip()
    if not value:
        raise MailError("Ungültige Ordnerliste vom Mailserver.")
    if value.startswith('"'):
        result = []
        index = 1
        while index < len(value):
            char = value[index]
            if char == '"':
                return "".join(result), value[index + 1:]
            if char == "\\":
                index += 1
                if index == len(value):
                    break
                char = value[index]
            result.append(char)
            index += 1
        raise MailError("Ungültige Ordnerliste vom Mailserver.")
    match = re.match(r"([^\s]+)(.*)", value)
    if match is None:
        raise MailError("Ungültige Ordnerliste vom Mailserver.")
    atom, rest = match.groups()
    return (None if atom.upper() == "NIL" else atom), rest


def _list_folder(record: Any) -> dict[str, Any]:
    literal = None
    if isinstance(record, tuple) and len(record) == 2:
        record, literal = record
    try:
        line = record.decode("utf-8") if isinstance(record, bytes) else str(record)
        match = re.match(r"^\(([^)]*)\)\s+(.*)$", line)
        if not match:
            raise MailError("Ungültige Ordnerliste vom Mailserver.")
        attributes = match[1].split()
        delimiter, rest = _list_string(match[2])
        if literal is None:
            name, trailing = _list_string(rest)
            if trailing.strip():
                raise MailError("Ungültige Ordnerliste vom Mailserver.")
        else:
            if not re.fullmatch(r"\s*\{\d+\}\s*", rest):
                raise MailError("Ungültige Ordnerliste vom Mailserver.")
            name = literal.decode("utf-8") if isinstance(literal, bytes) else str(literal)
        if name is None:
            raise MailError("Ungültige Ordnerliste vom Mailserver.")
        _folder_argument(name)
        return {"name": name, "attributes": attributes, "delimiter": delimiter, "historical": False,
                "gesendet": ist_gesendet_ordner(name, attributes)}
    except (UnicodeDecodeError, ValueError) as exc:
        raise MailError("Ungültige Ordnerliste vom Mailserver.") from exc


def _hat_flag(flags: str, flag: str) -> bool:
    """Ob die FLAGS-Angabe der Antwort das Flag trägt (ohne Groß/Klein, als ganzes Wort)."""
    # `flags` ist die `str()` der Bytes-Antwort: Backslashes stehen dort verdoppelt, deshalb ohne sie vergleichen.
    match = re.search(r"FLAGS\s*\(([^)]*)\)", flags or "", re.IGNORECASE)
    return bool(match) and flag.lstrip("\\").lower() in {wort.lstrip("\\").lower() for wort in match[1].split()}


def _gmail_extension(imap: Any) -> bool:
    return any((value.decode("ascii", errors="ignore") if isinstance(value, bytes) else str(value)).upper()
               == "X-GM-EXT-1" for value in getattr(imap, "capabilities", ()))


def _fetch_number(fetched: list[Any], name: str, maximum: int, *, minimum: int = 1) -> str:
    pattern = rb"\b" + name.encode("ascii") + rb"\s+([^\s()]+)"
    for part in fetched:
        metadata = part[0] if isinstance(part, tuple) else part
        if isinstance(metadata, bytes):
            match = re.search(pattern, metadata, re.IGNORECASE)
            if match:
                raw = match[1]
                if len(raw) > len(str(maximum)) or not raw.isdigit() or not minimum <= int(raw) <= maximum:
                    raise MailError("Ungültige Nachrichtenmetadaten vom Mailserver.")
                return str(int(raw))
    return ""


class _Sitzung:
    """Eine wiederverwendete Verbindung samt gewähltem Ordner."""

    def __init__(self, connector: MailConnector) -> None:
        self._connector = connector
        self._stack: ExitStack | None = None
        self._imap: Any = None
        self.folder: str | None = None
        # Die UIDVALIDITY des gewählten Ordners. `imaplib.response()` entnimmt die Antwort des Servers beim Lesen;
        # ein normgerechter Server schickt sie nur bei SELECT/EXAMINE. Wer den Ordner ohne neues SELECT weiterbenutzt,
        # fände sie sonst nicht mehr (Fremdprobe 3, Befund 1: keine Mail kam an).
        self._gueltigkeit: list[Any] | None = None

    def _connect(self) -> None:
        self._stack = ExitStack()
        try:
            self._imap = self._stack.enter_context(self._connector._open())
        except BaseException:
            self._stack.close()
            self._stack = None
            raise
        self.folder = None
        self._gueltigkeit = None

    def close(self) -> None:
        stack, self._stack, self._imap, self.folder = self._stack, None, None, None
        self._gueltigkeit = None
        if stack is not None:
            try:
                stack.close()
            except Exception:  # noqa: BLE001 - eine tote Verbindung lässt sich nicht mehr abmelden
                pass

    def select(self, ordner: str, frisch: bool = True) -> str:
        if not frisch and self.folder == ordner:
            gemerkt = getattr(self._imap, "untagged_responses", None)
            if self._gueltigkeit and isinstance(gemerkt, dict):
                gemerkt["UIDVALIDITY"] = list(self._gueltigkeit)
            return "OK"
        self.folder = None
        self._gueltigkeit = None
        status = self._imap.select(ordner, readonly=True)[0]
        if status == "OK":
            self.folder = ordner
            # Nur ansehen, nicht entnehmen: `_mailbox_validity` liest sie danach wie bisher.
            gemerkt = getattr(self._imap, "untagged_responses", None)
            self._gueltigkeit = list(gemerkt.get("UIDVALIDITY") or []) or None if isinstance(gemerkt, dict) else None
        return status

    def run(self, work: Callable[[Any, Callable[..., Any]], Any]) -> Any:
        """`work(imap, waehle)`; bei Verbindungsabbruch einmal neu verbinden und wiederholen.

        Nur echte Verbindungsfehler lösen das aus. Antworten des Servers wie
        „Ordner nicht gefunden“ (`IMAP4.error`) sind keine Abbrüche.
        """
        for versuch in (1, 2):
            if self._imap is None:
                self._connect()
            try:
                return work(self._imap, self.select)
            except (imaplib.IMAP4.abort, OSError, ssl.SSLError):
                self.close()
                if versuch == 2:
                    raise


class MailConnector:
    """Liest Nachrichten und versendet sie — Versand nur über die Freigabe."""

    #: Die Bestandsaufnahme kann von oben nach unten gehen (`inventory_page(…, absteigend=True)`): Die Aufnahme
    #: erfasst so die neuesten Mails zuerst. Leser ohne diese Angabe (Microsoft, Attrappen) bleiben aufsteigend.
    bestand_neueste_zuerst = True

    def __init__(self, config: MailConfig) -> None:
        self._config = config
        self._context: ssl.SSLContext | None = None
        # Texterkennung für gescannte Anhänge: nur, wenn ein lokales OCR-Modell eingerichtet ist (`anhaenge.ocr_fuer`).
        self.ocr = None
        # Die Sitzung gehört dem Thread, der sie geöffnet hat: Andere Threads
        # (Antworten im Gespräch, Prüfbereich) öffnen weiter ihre eigene Verbindung.
        self._local = threading.local()

    def _ssl_context(self) -> ssl.SSLContext:
        """Der Zertifikatskontext wird einmal gebaut (rund 23 ms), nicht je Abruf."""
        if self._context is None:
            self._context = ssl.create_default_context()
        return self._context

    @contextmanager
    def _open(self):
        """Eine angemeldete Verbindung; beim Verlassen sauber abgemeldet."""
        self._ruht_nicht()
        with imaplib.IMAP4_SSL(
            self._config.imap_host, self._config.imap_port,
            ssl_context=self._ssl_context(), timeout=30,
        ) as imap:
            self._login(imap)
            yield imap

    @contextmanager
    def session(self):
        """Mehrere Abrufe dieses Threads über eine Verbindung.

        Die Verbindung wird erst beim ersten Abruf geöffnet und beim Verlassen
        geschlossen. Bricht sie mitten im Durchgang ab, verbindet die Sitzung
        einmal neu (siehe `_Sitzung.run`). Verschachtelt gilt die äußere.
        """
        if getattr(self._local, "session", None) is not None:
            yield self._local.session
            return
        sitzung = _Sitzung(self)
        self._local.session = sitzung
        try:
            yield sitzung
        finally:
            self._local.session = None
            sitzung.close()

    def _with_imap(self, work: Callable[[Any, Callable[..., Any]], Any]) -> Any:
        """Führt `work(imap, waehle)` über die Sitzung aus, sonst über eine eigene Verbindung.

        `waehle(ordner, frisch=True)` wählt den Ordner schreibgeschützt. Mit
        `frisch=False` wird ein schon gewählter Ordner nicht erneut gewählt
        (reicht für Abrufe nach UID; die Bestandsaufnahme braucht frische Zähler).
        """
        sitzung = getattr(self._local, "session", None)
        if sitzung is not None:
            return sitzung.run(work)
        with self._open() as imap:
            return work(imap, lambda ordner, frisch=True: imap.select(ordner, readonly=True)[0])

    def pruefe_anmeldung(self, timeout: float = 8.0) -> None:
        """Meldet sich einmal an und wieder ab. Wirft die Fehler von `imaplib`, `ssl` und `socket` unverändert.

        Für die Prüfung beim Verbinden (`mail_anmeldung.py`): kurze Netzzeitgrenze statt der 30 s der Abrufe.
        """
        with imaplib.IMAP4_SSL(
            self._config.imap_host, self._config.imap_port,
            ssl_context=self._ssl_context(), timeout=timeout,
        ) as imap:
            self._login(imap, ausdruecklich=True)

    def _ruhe_schluessel(self) -> tuple[str, int, str, str]:
        if self._config.access_token:
            fingerabdruck = 'oauth'  # das Token wechselt stündlich; „Neu anmelden“ vergisst die Ruhe ausdrücklich
        else:
            fingerabdruck = hashlib.sha256((self._config.password or '').encode('utf-8')).hexdigest()
        return ((self._config.imap_host or '').strip().lower(), int(self._config.imap_port),
                (self._config.username or '').casefold(), fingerabdruck)

    def anmeldung_ruht(self) -> bool:
        """Ob der Server diese Zugangsdaten eben abgelehnt hat (echte Ablehnung, nicht vorübergehend)."""
        ruht, echt = ANMELDERUHE.ruht(self._ruhe_schluessel())
        return ruht and echt

    def _ruht_nicht(self) -> None:
        """Vor jedem Verbindungsaufbau: Ruhen diese Zugangsdaten, gar nicht erst verbinden (`_Anmelderuhe`)."""
        ANMELDERUHE.pruefen(self._ruhe_schluessel())

    def _login(self, imap, *, ausdruecklich: bool = False):
        schluessel = self._ruhe_schluessel()
        if not ausdruecklich:
            ANMELDERUHE.pruefen(schluessel)
        try:
            if self._config.access_token:
                token = self._config.access_token()
                payload = f"user={self._config.username}\x01auth=Bearer {token}\x01\x01".encode()
                sent = False
                def response(_challenge):
                    nonlocal sent
                    if sent:
                        return b""
                    sent = True
                    return payload
                imap.authenticate("XOAUTH2", response)
            else:
                imap.login(self._config.username, self._config.password)
        except imaplib.IMAP4.abort:
            raise  # Verbindung abgebrochen: keine Aussage über die Anmeldung.
        except AnmeldungAbgelehnt:
            raise
        except imaplib.IMAP4.error as exc:
            # Gekennzeichnet, nicht umgedeutet: Text und Klasse von `imaplib` bleiben (`mail_anmeldung.einordnen`).
            from ..mail_anmeldung import einordnen
            ANMELDERUHE.abgelehnt(schluessel, echt=einordnen(exc, self._config.imap_host).grund != 'nicht_erreichbar')
            raise AnmeldungAbgelehnt(*exc.args) from exc
        ANMELDERUHE.gelungen(schluessel)

    # -- Lesen -------------------------------------------------------------

    def folders(self) -> list[dict[str, Any]]:
        """Wählbare Ordner; Papierkorb/Spam sind keine Aufnahmequellen.

        `historical` markiert die Startordner: den Gmail-/SPECIAL-USE-Ordner
        für alle Nachrichten (er enthält Gesendet schon), sonst INBOX **und**
        den Gesendet-Ordner (`gesendet`: SPECIAL-USE `\\Sent`, sonst der erste
        mit einem üblichen Namen, `GESENDET_NAMEN`). Ein Stabschef kennt die
        eigenen Zusagen; ohne Gesendet fehlen sie bei jedem Konto außer Gmail
        und Microsoft 365. Namen bleiben in der vom Server gelieferten
        IMAP-Kodierung, damit auch modifiziertes UTF-7 beim späteren SELECT
        unverändert funktioniert.
        """
        try:
            self._ruht_nicht()
            with imaplib.IMAP4_SSL(
                self._config.imap_host, self._config.imap_port,
                ssl_context=self._ssl_context(), timeout=30,
            ) as imap:
                self._login(imap)
                status, data = imap.list()
                if status != "OK":
                    raise MailError("Mailordner konnten nicht ermittelt werden.")
                folders = []
                names = set()
                for record in data or []:
                    if record is None or record == b"":
                        continue
                    folder = _list_folder(record)
                    attributes = {value.lower() for value in folder["attributes"]}
                    name = folder["name"]
                    leaf = name.rsplit(folder["delimiter"], 1)[-1] if folder["delimiter"] else name
                    if attributes & {"\\noselect", "\\nonexistent", "\\trash", "\\junk"} or leaf.lower() in {"trash", "junk", "spam"}:
                        continue
                    if name not in names:
                        folders.append(folder)
                        names.add(name)
                historical = next((folder for folder in folders if "\\all" in
                                   {value.lower() for value in folder["attributes"]}), None)
                if historical is None:
                    historical = next((folder for folder in folders if folder["name"].lower() in
                                       {"[gmail]/all mail", "[google mail]/all mail"}), None)
                if historical is None:
                    historical = next((folder for folder in folders if folder["name"].upper() == "INBOX"), None)
                    # Ohne Gesamtbestand kommt Gesendet dazu: das Attribut zuerst, sonst der erste übliche Name.
                    gesendet = next((folder for folder in folders if "\\sent" in
                                     {value.lower() for value in folder["attributes"]}), None)
                    if gesendet is None:
                        gesendet = next((folder for folder in folders if folder["gesendet"]), None)
                    if gesendet is not None and gesendet is not historical:
                        gesendet["historical"] = True
                if historical is not None:
                    historical["historical"] = True
                return folders
        except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
            raise MailError(f"IMAP-Zugriff fehlgeschlagen: {exc}") from exc

    def inventory_page(
        self, folder: str, after_uid: int = 0, before_uid: int | None = None,
        limit: int = 100, *, uidvalidity: str | None = None, absteigend: bool = False,
    ) -> dict[str, Any]:
        """Ein begrenztes UID-Fenster für eine fortsetzbare Bestandsaufnahme.

        `before_uid` ist eine inklusive, beim ersten Aufruf aus UIDNEXT-1
        gelesene Momentaufnahme. `limit` begrenzt den numerischen Suchbereich,
        nicht die Zahl tatsächlich vorhandener Nachrichten. `next_uid` ist
        dessen obere Grenze und schreitet auch bei vollständig gelöschten
        Bereichen voran. Erst nach erfolgreicher Verarbeitung der ganzen
        Seite darf der Aufrufer sie speichern; `done` richtet sich nach der
        Scan-Grenze. Bei Fortsetzungen kann `uidvalidity` eine alte Generation
        vor jeder Suche zurückweisen.

        `absteigend=True`: Neueste zuerst. Offen ist der Bereich (`after_uid`,
        obere Grenze]; das Fenster liegt an seinem oberen Ende, also
        (max(`after_uid`, obere Grenze − `limit`), obere Grenze]. Dessen untere
        Grenze kommt als `next_before_uid` zurück und ist die obere Grenze des
        nächsten Aufrufs; `next_uid` bleibt `after_uid`. `done`, sobald sie
        `after_uid` erreicht. So bleibt eine aufsteigend begonnene
        Bestandsaufnahme (unten bis `after_uid` erfasst) ohne Lücke und ohne
        Doppelung fortsetzbar.
        """
        selected_folder = _folder_argument(folder)
        if type(after_uid) is not int:
            raise ValueError("Ungültiger Mail-Fortschritt.")
        for number in (after_uid, before_uid):
            if number is not None and (type(number) is not int or not 0 <= number <= MAX_UID):
                raise ValueError("Ungültiger Mail-Fortschritt.")
        if type(limit) is not int or not 1 <= limit <= MAX_INVENTORY_WINDOW:
            raise ValueError("Pro Durchgang sind 1 bis 1000 UID-Positionen zulässig.")
        if uidvalidity is not None and (not isinstance(uidvalidity, str) or not uidvalidity.isascii()
                                       or not uidvalidity.isdigit() or not 0 < int(uidvalidity) <= MAX_UID):
            raise ValueError("Ungültige Postfachgeneration.")
        if type(absteigend) is not bool:
            raise ValueError("Ungültige Richtung der Bestandsaufnahme.")
        def lesen(imap, waehle):
            # Frisch wählen: UIDNEXT muss den heutigen Stand zeigen, nicht den der Sitzung.
            if waehle(selected_folder, True) != "OK":
                raise MailError("Mailordner konnte nicht geöffnet werden.")
            validity = _mailbox_validity(imap)
            if uidvalidity is not None and validity != uidvalidity:
                raise MailboxGenerationChanged("Die Postfachgeneration ist veraltet. Bitte die Bestandsaufnahme neu starten.")
            upper = _mailbox_number(imap, "UIDNEXT", MAX_UID + 1) - 1
            if before_uid is not None:
                upper = min(upper, before_uid)
            if absteigend:
                # Das Fenster am oberen Ende des offenen Bereichs: die jüngsten Nummern zuerst.
                unten = max(after_uid, upper - limit) if after_uid < upper else min(after_uid, upper)
                von, bis = unten, upper
            else:
                von, bis = after_uid, (min(after_uid + limit, upper) if after_uid < upper else after_uid)
            numbers = set()
            if von < bis:
                status, data = imap.uid("search", None, "UID", f"{von + 1}:{bis}")
                if status != "OK":
                    raise MailError("Nachrichtenbestand konnte nicht ermittelt werden.")
                for raw in (data[0].split() if data and data[0] else []):
                    if not raw.isdigit() or not 0 < int(raw) <= MAX_UID:
                        raise MailError("Ungültige Nachrichtenkennung vom Mailserver.")
                    number = int(raw)
                    if von < number <= bis:
                        numbers.add(number)
            if absteigend:
                return {"folder": folder, "uidvalidity": validity, "upper_uid": upper, "uids": sorted(numbers),
                        "next_uid": after_uid, "next_before_uid": von, "done": von <= after_uid}
            return {"folder": folder, "uidvalidity": validity, "upper_uid": upper,
                    "uids": sorted(numbers), "next_uid": bis, "done": bis >= upper}

        try:
            return self._with_imap(lesen)
        except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
            raise MailError(f"IMAP-Zugriff fehlgeschlagen: {exc}") from exc

    def inbox(self, limit: int = 10, unread_only: bool = False) -> list[Message]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Pro Abruf sind 1 bis 100 Nachrichten zulässig.')
        criteria = "UNSEEN" if unread_only else "ALL"
        try:
            self._ruht_nicht()
            with imaplib.IMAP4_SSL(
                self._config.imap_host, self._config.imap_port,
                ssl_context=self._ssl_context(), timeout=30,
            ) as imap:
                self._login(imap)
                imap.select("INBOX", readonly=True)  # readonly: nichts als gelesen markieren
                validity = _mailbox_validity(imap)
                status, data = imap.uid("search", None, criteria)
                if status != "OK":
                    raise MailError(f"Suche fehlgeschlagen: {status}")

                found = data[0].split() if data and data[0] else []
                valid_uids = set()
                for raw_uid in found:
                    if not raw_uid.isdigit() or len(raw_uid) > len(str(MAX_UID)):
                        continue
                    uid_number = int(raw_uid)
                    if 0 < uid_number <= MAX_UID:
                        valid_uids.add(uid_number)
                uids = [str(uid).encode("ascii") for uid in sorted(valid_uids)[-limit:]]
                if not uids:
                    return []

                fields = f"(UID FLAGS RFC822.SIZE BODY.PEEK[]<0.{MAX_INBOX_PREVIEW_BYTES}>)"
                status, fetched = imap.uid("fetch", b",".join(uids), fields)
                if status != "OK":
                    raise MailError(f"Abruf fehlgeschlagen: {status}")
                requested = {int(uid) for uid in uids}
                by_uid: dict[int, tuple[bytes, bytes]] = {}
                duplicate_uids: set[int] = set()
                for part in fetched or []:
                    if not isinstance(part, tuple) or len(part) < 2 or not isinstance(part[1], bytes):
                        continue
                    header = part[0]
                    if isinstance(header, bytes):
                        header_bytes = header
                    elif isinstance(header, str):
                        header_bytes = header.encode("ascii", errors="replace")
                    else:
                        continue
                    matches = list(re.finditer(
                        rb"(?:^|[\t (])UID[\t ]+([0-9]+)(?=[\t )])",
                        header_bytes,
                        re.IGNORECASE,
                    ))
                    if len(matches) != 1:
                        continue
                    uid_bytes = matches[0].group(1)
                    if len(uid_bytes) > len(str(MAX_UID)):
                        continue
                    uid_number = int(uid_bytes)
                    if uid_number not in requested or uid_number in duplicate_uids:
                        continue
                    if uid_number in by_uid:
                        by_uid.pop(uid_number, None)
                        duplicate_uids.add(uid_number)
                        continue
                    by_uid[uid_number] = (header_bytes, part[1])

                messages = []
                for uid in reversed(uids):
                    uid_number = int(uid)
                    fetched_message = by_uid.get(uid_number)
                    if fetched_message is None:
                        continue
                    flags_header, raw = fetched_message
                    parsed = email.message_from_bytes(raw[:MAX_INBOX_PREVIEW_BYTES])
                    reported_size = _fetch_number([(flags_header, raw)], "RFC822.SIZE", 2**63 - 1, minimum=0)
                    clipped = (len(raw) > MAX_INBOX_PREVIEW_BYTES
                               or bool(reported_size and int(reported_size) > len(raw))
                               or (not reported_size and len(raw) >= MAX_INBOX_PREVIEW_BYTES))
                    flags = flags_header.decode("ascii", errors="replace")
                    messages.append(Message(
                        uid=f"{validity}.{uid_number}",
                        subject=_decode(parsed.get("Subject")),
                        sender=_decode(parsed.get("From")),
                        date=self._parse_date(parsed.get("Date")),
                        preview=" ".join(_body(parsed, limit=1200).split())[:300],
                        unread="\\Seen" not in flags,
                        truncated=clipped,
                        spam_flag=any(str(value).strip().lower().startswith(('yes', 'true')) for key in ('X-Spam-Flag','X-Spam-Status') for value in parsed.get_all(key, [])),
                        list_mail=bool(parsed.get('List-Id') or parsed.get('List-Unsubscribe') or str(parsed.get('Precedence','')).lower() in ('bulk','list')),
                    ))
                return messages
        except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
            raise MailError(f"IMAP-Zugriff fehlgeschlagen: {exc}") from exc

    def pending_uids(self, after: str | None = None, limit: int = 50) -> list[str]:
        """Nächste Kennungen in Verarbeitungsreihenfolge, ohne Cursor vorzugreifen.

        Der Aufrufer darf erst nach erfolgreicher Quellenaufnahme die letzte
        Kennung speichern. Ein neues UIDVALIDITY beginnt wieder beim Anfang.
        """
        if not 1 <= limit <= 200:
            raise ValueError("Pro Durchgang sind 1 bis 200 Nachrichten zulässig.")
        previous_validity, last_uid = None, 0
        if after is not None:
            previous_validity, separator, number = after.partition(".")
            if not separator or not previous_validity.isascii() or not previous_validity.isdigit() or not number.isascii() or not number.isdigit():
                raise ValueError("Ungültiger Mail-Fortschritt.")
            last_uid = int(number)
            if not 0 < int(previous_validity) <= 4294967295 or not 0 < last_uid <= 4294967295:
                raise ValueError("Ungültiger Mail-Fortschritt.")
        try:
            self._ruht_nicht()
            with imaplib.IMAP4_SSL(
                self._config.imap_host, self._config.imap_port,
                ssl_context=self._ssl_context(), timeout=30,
            ) as imap:
                self._login(imap)
                status, _ = imap.select("INBOX", readonly=True)
                if status != "OK":
                    raise MailError("Posteingang konnte nicht geöffnet werden.")
                validity = _mailbox_validity(imap)
                if previous_validity != validity:
                    last_uid = 0
                if last_uid == 4294967295:
                    return []
                status, data = imap.uid("search", None, "UID", f"{last_uid + 1}:*")
                if status != "OK":
                    raise MailError("Neue Nachrichten konnten nicht ermittelt werden.")
                # IMAP-Bereiche können auch rückwärts gelten: n:* kann die
                # letzte alte UID liefern. Deshalb zusätzlich strikt filtern.
                numbers = set()
                for raw in (data[0].split() if data and data[0] else []):
                    if not raw.isdigit():
                        raise MailError("Ungültige Nachrichtenkennung vom Mailserver.")
                    value = int(raw)
                    if not 0 < value <= 4294967295:
                        raise MailError("Ungültige Nachrichtenkennung vom Mailserver.")
                    if value > last_uid:
                        numbers.add(value)
                return [f"{validity}.{number}" for number in sorted(numbers)[:limit]]
        except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
            raise MailError(f"IMAP-Zugriff fehlgeschlagen: {exc}") from exc

    def message(self, uid: str) -> Message:
        """Eine einzelne Nachricht mit vollem Text.

        `readonly=True` wie beim Posteingang: Etwas anzusehen darf es nicht als
        gelesen markieren. Wer seine Mail woanders bearbeitet, soll dort
        denselben Zustand vorfinden — Icarus schaut zu, es räumt nicht auf.
        """
        return self.message_in_folder("INBOX", uid)

    def message_mit_anhaengen(self, folder: str, uid: str) -> Message:
        """Wie `message_in_folder`, dazu die gelesenen Anhänge (`anhaenge.py`). Für die Aufnahme, nicht zum Ansehen."""
        return self.message_in_folder(folder, uid, anhaenge=True)

    def message_in_folder(self, folder: str, uid: str, *, anhaenge: bool = False) -> Message:
        """Eine Mail aus einem bestimmten Ordner; UIDVALIDITY bleibt Pflicht."""
        selected_folder = _folder_argument(folder)
        roh: dict[str, Any] = {}

        def abrufen(imap, waehle):
            # Ein schon gewählter Ordner bleibt in der Sitzung gewählt: Der Abruf geht nach UID.
            if waehle(selected_folder, False) != "OK":
                raise MailError("Mailordner konnte nicht geöffnet werden.")
            validity, separator, remote_uid = str(uid).partition(".")
            if not separator or not remote_uid.isascii() or not remote_uid.isdigit() or not 0 < int(remote_uid) <= MAX_UID:
                raise MailError("Die Nachrichtenkennung ist veraltet. Bitte den Posteingang neu laden.")
            if validity != _mailbox_validity(imap):
                raise MailboxGenerationChanged("Die Nachrichtenkennung ist veraltet. Bitte den Posteingang neu laden.")
            gmail = _gmail_extension(imap)
            partial = f"BODY.PEEK[]<0.{MAX_MESSAGE_WIRE_BYTES + 1}>"
            fields = f"(UID FLAGS RFC822.SIZE {partial}{' X-GM-MSGID' if gmail else ''})"
            status, fetched = imap.uid("fetch", remote_uid.encode(), fields)
            if status != "OK" or not fetched or fetched[0] is None:
                raise MailError(f"Nachricht {uid} nicht gefunden.")
            raw = next(
                (part[1] for part in fetched
                 if isinstance(part, tuple) and isinstance(part[1], bytes)),
                None,
            )
            if raw is None:
                raise MailError(f"Nachricht {uid} nicht lesbar.")
            received_uid = _fetch_number(fetched, "UID", MAX_UID)
            if received_uid and int(received_uid) != int(remote_uid):
                raise MailError("Die gelieferte Mail passt nicht zur angefragten Kennung.")
            reported_size = _fetch_number(fetched, "RFC822.SIZE", 2**63 - 1, minimum=0)
            wire_truncated = len(raw) > MAX_MESSAGE_WIRE_BYTES or bool(
                reported_size and int(reported_size) > len(raw))
            parsed = email.message_from_bytes(raw[:MAX_MESSAGE_WIRE_BYTES])
            roh.update(parsed=parsed, abgeschnitten=wire_truncated)
            flags = str(fetched[0][0]) if isinstance(fetched[0], tuple) else ""
            text = _body(parsed, limit=FULL_BODY_LIMIT + 1)
            return Message(
                uid=str(uid),
                subject=_decode(parsed.get("Subject")),
                sender=_decode(parsed.get("From")),
                date=self._parse_date(parsed.get("Date")),
                preview=" ".join(text.split())[:300],
                unread="\\Seen" not in flags,
                entwurf=_hat_flag(flags, "\\Draft"),
                body=text[:FULL_BODY_LIMIT],
                truncated=wire_truncated or len(text) > FULL_BODY_LIMIT,
                spam_flag=any(str(value).strip().lower().startswith(('yes', 'true')) for key in ('X-Spam-Flag','X-Spam-Status') for value in parsed.get_all(key, [])),
                list_mail=bool(parsed.get('List-Id') or parsed.get('List-Unsubscribe') or str(parsed.get('Precedence','')).lower() in ('bulk','list')),
                message_id=(parsed.get("Message-ID") or "").strip(),
                reply_to=_decode(parsed.get("Reply-To")),
                in_reply_to=(parsed.get("In-Reply-To") or "")[:16000],
                references=tuple(re.findall(r"<[^<>\s]{1,500}>", (parsed.get("References") or "")[:16000])[:64]),
                provider_id=_fetch_number(fetched, "X-GM-MSGID", 2**64 - 1) if gmail else "",
                recipients=_empfaenger(parsed),
                own_addresses=self._own_addresses(),
            )

        try:
            nachricht = self._with_imap(abrufen)
        except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
            raise MailError(f"IMAP-Zugriff fehlgeschlagen: {exc}") from exc
        if anhaenge and roh.get('parsed') is not None:
            # Außerhalb der IMAP-Sitzung: Eine PDF zu lesen dauert, die Verbindung soll dabei nicht warten.
            from dataclasses import replace
            from ..anhaenge import aus_mail
            bericht: dict[str, Any] = {}
            nachricht = replace(nachricht, anhaenge=aus_mail(roh['parsed'], abgeschnitten=roh['abgeschnitten'],
                                                             ocr=self.ocr, bericht=bericht), anhang_bericht=bericht)
        return nachricht

    @staticmethod
    def _parse_date(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            parsed = email.utils.parsedate_to_datetime(raw)
            # -0000 is UTC with unknown original local timezone; Python returns
            # a naive datetime. Use the same UTC fallback for missing zones so
            # sorting and display never depend on the container's local timezone.
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except (TypeError, ValueError):
            return None

    # -- Senden ------------------------------------------------------------

    def _own_addresses(self) -> tuple[str, ...]:
        """Benutzername und Absenderadresse dieses Kontos, soweit es Adressen sind."""
        from email.utils import parseaddr
        adressen = []
        for wert in (self._config.username, self._config.from_address):
            adresse = parseaddr(wert or "")[1].strip().casefold()
            if "@" in adresse and adresse not in adressen:
                adressen.append(adresse)
        return tuple(adressen)

    def sender_label(self, account_id: str = "") -> str:
        return self._config.sender

    def send(
        self, to: str, subject: str, body: str, in_reply_to: str = ""
    ) -> str:
        """Versendet eine Mail. Wird ausschließlich nach erteilter Freigabe gerufen."""
        if not self._config.smtp_host:
            raise MailError("Kein SMTP-Server konfiguriert (ICARUS_SMTP_HOST).")

        message = EmailMessage()
        message["From"] = self._config.sender
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = email.utils.formatdate(localtime=True)
        message["Message-ID"] = email.utils.make_msgid()
        if in_reply_to:
            # Ohne diese beiden Köpfe erscheint eine Antwort beim Empfänger als
            # neue Nachricht statt im Verlauf. Das ist kein Schönheitsfehler:
            # Wer zwanzig Mails am Tag bekommt, findet sie dann nicht wieder.
            message["In-Reply-To"] = in_reply_to
            message["References"] = in_reply_to
        message.set_content(body)

        try:
            with smtplib.SMTP(self._config.smtp_host, self._config.smtp_port, timeout=30) as smtp:
                smtp.starttls(context=self._ssl_context())
                if self._config.access_token:
                    token = self._config.access_token()
                    payload = f"user={self._config.username}\x01auth=Bearer {token}\x01\x01"
                    smtp.auth("XOAUTH2", lambda challenge=None: payload if challenge is None else "")
                else:
                    smtp.login(self._config.username, self._config.password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            raise MailError(f"Versand fehlgeschlagen: {exc}") from exc

        return f"Gesendet an {to}."


__all__ = ["MailConfig", "MailConnector", "MailError", "MailboxGenerationChanged", "Message", "GESENDET_NAMEN",
           "ist_gesendet_ordner"]
