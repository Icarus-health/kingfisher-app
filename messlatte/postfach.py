"""Ein Postfach, das nur den Netzwerkteil von IMAP ersetzt.

Das Produkt holt Mail über `connectors/mail.py::MailConnector` und
`mail_intake.py::Intake`. Beide sind Produktlogik: Kopfzeilen dekodieren,
Textteil wählen, Größen begrenzen, UIDVALIDITY prüfen, Fortschritt merken,
Wiederholung nach Fehlern. Deshalb setzt die Messlatte **unterhalb** von ihnen an:
Ersetzt wird allein `imaplib.IMAP4_SSL`, also die Verbindung zum Server. Der
Server liefert echte RFC-822-Rohmails, die aus der Welt gebaut werden.

**Grenze:** Es gibt keinen TLS-Handshake (auch der Zertifikatskontext entfällt),
keine Anmeldung, keine
Serverbesonderheiten (Gmail-Erweiterungen, Ordnernamen in modifiziertem UTF-7,
HTML-Teile). Mails sind schlichter `text/plain`-Text; PDF-Anhänge der Welt (`anhaenge`)
hängen als `application/pdf` daran, erzeugt von `pdf.py`.
"""
from __future__ import annotations

import imaplib
import re
from contextlib import contextmanager
from email.message import EmailMessage
from email.utils import format_datetime, formataddr
from typing import Iterator

from .daten import Mail

VALIDITY = 1
MESSAGE_ID_SUFFIX = '@messlatte.example'


def message_id(quelle_id: str) -> str:
    return f'<{quelle_id}{MESSAGE_ID_SUFFIX}>'


def quelle_aus_message_id(wert: str) -> str | None:
    """Umkehrung: aus `<mainz-003@messlatte.example>` (auch mit Kontopräfix) die Welt-ID; ein Anhang der Mail
    (`…#anhang:2:Rechnung.pdf`) heißt `mainz-003#anhang-2`."""
    treffer = re.search(r'<([^<>@\s]+)' + re.escape(MESSAGE_ID_SUFFIX) + r'>(?:#anhang:(\d+):)?', wert or '')
    if not treffer:
        return None
    return f'{treffer.group(1)}#anhang-{treffer.group(2)}' if treffer.group(2) else treffer.group(1)


def rohmail(mail: Mail) -> bytes:
    """Die Mail so, wie ein Server sie ausliefern würde (RFC 822, UTF-8)."""
    nachricht = EmailMessage()
    nachricht['From'] = formataddr((mail.von.name, mail.von.adresse))
    nachricht['To'] = ', '.join(formataddr((a.name, a.adresse)) for a in mail.an)
    if mail.cc:
        nachricht['Cc'] = ', '.join(formataddr((a.name, a.adresse)) for a in mail.cc)
    nachricht['Subject'] = mail.betreff
    nachricht['Date'] = format_datetime(mail.zeit)
    nachricht['Message-ID'] = message_id(mail.id)
    if mail.antwort_auf:
        nachricht['In-Reply-To'] = message_id(mail.antwort_auf)
        nachricht['References'] = message_id(mail.antwort_auf)
    nachricht.set_content(mail.text)
    from .pdf import scan_pdf, text_pdf
    for anhang in mail.anhaenge:
        daten = text_pdf([list(z) for z in anhang.seiten]) if anhang.seiten else scan_pdf(anhang.gescannt)
        nachricht.add_attachment(daten, maintype='application', subtype='pdf', filename=anhang.datei)
    return nachricht.as_bytes()


class Postfach:
    """Ordner mit Mails und laufenden UIDs (ab 1). Ein Konto, feste UIDVALIDITY."""

    def __init__(self) -> None:
        self.ordner: dict[str, list[tuple[int, bytes]]] = {}
        # (Ordner, UID) -> Welt-ID, für die Zuordnung nach der Aufnahme
        self.welt_id: dict[tuple[str, int], str] = {}
        self.abrufe = 0
        # Wie oft das Produkt eine Verbindung aufgebaut hat (eine Sitzung holt viele Mails über eine).
        self.verbindungen = 0
        # Testhaken: UIDs, deren Abruf einmal scheitert (Fehlerwiederholung des Produkts)
        self.scheitern_einmal: set[tuple[str, int]] = set()
        # Testhaken: UIDs, deren Abruf immer scheitert (bleibt nach der Wiederholung „fehlgeschlagen“)
        self.scheitern_immer: set[tuple[str, int]] = set()

    def ablegen(self, ordner: str, quelle_id: str, roh: bytes) -> int:
        liste = self.ordner.setdefault(ordner, [])
        uid = len(liste) + 1
        liste.append((uid, roh))
        self.welt_id[(ordner, uid)] = quelle_id
        return uid

    def ablegen_mail(self, mail: Mail) -> int:
        return self.ablegen(mail.ordner, mail.id, rohmail(mail))

    def anzahl(self) -> int:
        return sum(len(v) for v in self.ordner.values())


def _ordnername(argument: str) -> str:
    """Macht das Anführungszeichen-Quoting von `_folder_argument` rückgängig."""
    if len(argument) >= 2 and argument[0] == argument[-1] == '"':
        return re.sub(r'\\(.)', r'\1', argument[1:-1])
    return argument


def _verbindung(postfach: Postfach):
    """Eine Ersatzklasse für `imaplib.IMAP4_SSL`, gebunden an dieses Postfach."""

    class Verbindung:
        capabilities: tuple = ()

        def __init__(self, host=None, port=None, *args, **kwargs):
            self._aktuell: str | None = None
            postfach.verbindungen += 1

        def __enter__(self):
            return self

        def __exit__(self, *ausnahme):
            return False

        def login(self, benutzer, passwort):
            return 'OK', [b'angemeldet']

        def authenticate(self, mechanismus, antwort):
            return 'OK', [b'angemeldet']

        def logout(self):
            return 'BYE', [b'']

        def select(self, ordner, readonly=False):
            name = _ordnername(ordner)
            if name not in postfach.ordner:
                return 'NO', [b'Ordner unbekannt']
            self._aktuell = name
            return 'OK', [str(len(postfach.ordner[name])).encode()]

        def response(self, name):
            liste = postfach.ordner[self._aktuell] if self._aktuell else []
            wert = {'UIDVALIDITY': VALIDITY, 'UIDNEXT': (liste[-1][0] if liste else 0) + 1}.get(name.upper())
            return (name, [str(wert).encode()]) if wert is not None else (name, [None])

        def uid(self, befehl, *argumente):
            liste = postfach.ordner[self._aktuell]
            if befehl.lower() == 'search':
                # imaplib: uid('search', None, 'UID', 'a:b')
                bereich = argumente[-1]
                unten, _, oben = str(bereich).partition(':')
                unten_n = int(unten)
                oben_n = int(oben) if oben.isdigit() else (liste[-1][0] if liste else 0)
                gefunden = [str(u).encode() for u, _ in liste if unten_n <= u <= oben_n]
                return 'OK', [b' '.join(gefunden)]
            if befehl.lower() == 'fetch':
                nummer = int(argumente[0])
                postfach.abrufe += 1
                if (self._aktuell, nummer) in postfach.scheitern_immer:
                    raise imaplib.IMAP4.abort('Verbindung abgebrochen (Test)')
                if (self._aktuell, nummer) in postfach.scheitern_einmal:
                    postfach.scheitern_einmal.discard((self._aktuell, nummer))
                    raise imaplib.IMAP4.abort('Verbindung abgebrochen (Test)')
                roh = next((r for u, r in liste if u == nummer), None)
                if roh is None:
                    return 'OK', [None]
                kopf = f'{nummer} (UID {nummer} FLAGS (\\Seen) RFC822.SIZE {len(roh)} BODY[]<0> {{{len(roh)}}}'
                return 'OK', [(kopf.encode(), roh), b')']
            raise NotImplementedError(f'IMAP-Befehl {befehl} ist in der Attrappe nicht vorgesehen')

    return Verbindung


@contextmanager
def postfach_installieren(postfach: Postfach) -> Iterator[Postfach]:
    """Ersetzt die Verbindung für die Dauer des Blocks und stellt danach alles wieder her.

    Ersetzt werden `imaplib.IMAP4_SSL` und `ssl.create_default_context`: Das Produkt
    baut vor **jedem** Abruf einen TLS-Kontext (Zertifikate laden, gut 20 ms). Der
    gehört zum Netzwerk, das hier fehlt, und würde bei zehntausenden Mails die
    Aufnahmezeit beherrschen.
    """
    import ssl
    original, kontext = imaplib.IMAP4_SSL, ssl.create_default_context
    imaplib.IMAP4_SSL = _verbindung(postfach)  # type: ignore[misc]
    ssl.create_default_context = lambda *args, **kwargs: None  # type: ignore[assignment]
    try:
        yield postfach
    finally:
        imaplib.IMAP4_SSL = original  # type: ignore[misc]
        ssl.create_default_context = kontext  # type: ignore[assignment]
