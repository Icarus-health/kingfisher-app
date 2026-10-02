"""Eine IMAP-Attrappe für Tests und Browserproben: echter TLS-Dienst auf 127.0.0.1, kein Netz nach außen.

Verhalten je `modus` (jederzeit änderbar):

* `annehmen`: Anmeldung mit dem richtigen Passwort gelingt; LIST liefert INBOX. Ohne `nachrichten` ist der Posteingang
  leer. Mit `nachrichten` (rohe Mails, UID = Position + 1) antworten EXAMINE/SELECT, `UID SEARCH` und `UID FETCH` wie
  ein normgerechter Server: `UIDVALIDITY` und `UIDNEXT` kommen **nur** als Antwort auf SELECT/EXAMINE, nie bei einem
  späteren Befehl (Fremdprobe 3, Befund 1: daran scheiterte die Aufnahme in der wiederverwendeten Sitzung).
* `ablehnen`: jede Anmeldung scheitert mit `NO [AUTHENTICATIONFAILED]` (wie ein falsches Passwort).
* `imap_aus`: jede Anmeldung scheitert mit dem ausdrücklichen Hinweis, dass IMAP ausgeschaltet ist.
* `google_ablehnen`: jede Anmeldung scheitert, wie Gmail ein normales Passwort ablehnt (`Invalid credentials (Failure)`).
* `stumm`: nimmt die Verbindung an und schweigt (kein TLS-Handschlag, keine Begrüßung) – ein Postfach, das nicht
  antwortet.
* `stumm_nach_anmeldung`: Anmeldung gelingt, danach bleibt jede Anfrage unbeantwortet.

Das Zertifikat ist selbst ausgestellt (für `127.0.0.1` und `localhost`, erzeugt mit `openssl`). Wer sich verbinden will, vertraut ihm über
`SSL_CERT_FILE=<attrappe.zertifikat>` (dann baut auch `ssl.create_default_context()` im Sidecar darauf) oder
über `client_kontext()`. Nur synthetische Zugänge.
"""
from __future__ import annotations

import re
import socket
import ssl
import subprocess
import tempfile
import threading
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path

PASSWORT = 'richtig-geheim'


def probe_mail(absender: str, betreff: str, text: str, *, an: str = 'lena.probe@example.org', minuten: int = 0,
               kopf: dict[str, str] | None = None) -> bytes:
    """Eine synthetische Mail als Rohtext (RFC 5322), wie ein Server sie liefert."""
    mail = EmailMessage()
    mail['From'], mail['To'], mail['Subject'] = absender, an, betreff
    mail['Date'] = format_datetime(datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc) + timedelta(minutes=minuten))
    mail['Message-ID'] = f'<probe-{minuten}@example.org>'
    for name, wert in (kopf or {}).items():
        mail[name] = wert
    mail.set_content(text)
    return bytes(mail)


def probe_postfach() -> list[bytes]:
    """Fünf synthetische Mails wie in Fremdprobe 3: zwei von Anna, eine von Jonas, ein Newsletter, eine Erinnerung."""
    return [
        probe_mail('Jonas Keller <jonas.keller@example.org>', 'Treffen am Montag',
                   'Hallo Lena,\n\npasst dir Montag um 10 Uhr für unser Treffen?\n\nJonas', minuten=0),
        probe_mail('Anna Berg <anna.berg@example.org>', 'Bitte: Angebot Vereinsfest bis Freitag',
                   'Liebe Lena,\n\nkannst du mir bis Freitag, 9. Oktober, das Angebot für das Vereinsfest schicken?'
                   '\n\nDanke, Anna', minuten=10),
        probe_mail('Gartenbrief <news@gartenbrief.example.org>', 'Gartenbrief Oktober',
                   'Die Tipps des Monats.', minuten=20,
                   kopf={'List-Unsubscribe': '<mailto:abmelden@gartenbrief.example.org>'}),
        probe_mail('Praxis Sonnenhof <praxis@sonnenhof.example.org>', 'Erinnerung an Ihren Termin',
                   'Wir erinnern an Ihren Termin am 12. Oktober um 9 Uhr.', minuten=30),
        probe_mail('Anna Berg <anna.berg@example.org>', 'Nachtrag: Aufbau',
                   'Lena, der Aufbau beginnt am Samstag um 8 Uhr.\n\nAnna', minuten=40),
    ]


def _zertifikat(ordner: Path) -> tuple[Path, Path]:
    """Selbst ausgestellt, zur Laufzeit erzeugt (openssl), damit kein Schlüssel im Repository liegt."""
    zert_pfad, schluessel_pfad = ordner / 'attrappe.pem', ordner / 'attrappe.key'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:prime256v1', '-nodes',
                    '-keyout', str(schluessel_pfad), '-out', str(zert_pfad), '-days', '30', '-subj', '/CN=IMAP-Attrappe',
                    '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
                    '-addext', 'basicConstraints=critical,CA:TRUE'],
                   check=True, capture_output=True, timeout=30)
    return zert_pfad, schluessel_pfad


class ImapAttrappe:
    def __init__(self, modus: str = 'annehmen', passwort: str = PASSWORT, *, nachrichten: list[bytes] | None = None,
                 uidvalidity: int = 1) -> None:
        self.modus = modus
        self.passwort = passwort
        self.anmeldungen: list[tuple[str, str]] = []
        #: Rohmails des Posteingangs; UID ist Position + 1, die Sequenznummer ebenso.
        self.nachrichten: list[bytes] = list(nachrichten or [])
        self.uidvalidity = uidvalidity
        #: Jeder Befehl nach der Anmeldung (ohne Marke), zum Nachsehen in Tests.
        self.befehle: list[str] = []
        self._ordner = Path(tempfile.mkdtemp(prefix='imap-attrappe-'))
        self.zertifikat, self._schluessel = _zertifikat(self._ordner)
        self._server_kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._server_kontext.load_cert_chain(self.zertifikat, self._schluessel)
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(('127.0.0.1', 0))
        self._sock.listen(16)
        self.port = self._sock.getsockname()[1]
        self._halt = threading.Event()
        self._offen: list[socket.socket] = []
        threading.Thread(target=self._annehmen, name='imap-attrappe', daemon=True).start()

    def client_kontext(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=str(self.zertifikat))

    def schliessen(self) -> None:
        self._halt.set()
        for s in [self._sock, *self._offen]:
            try:
                s.close()
            except OSError:
                pass

    def __enter__(self) -> 'ImapAttrappe':
        return self

    def __exit__(self, *_: object) -> None:
        self.schliessen()

    # -- Dienst --

    def _annehmen(self) -> None:
        while not self._halt.is_set():
            try:
                roh, _ = self._sock.accept()
            except OSError:
                return
            self._offen.append(roh)
            threading.Thread(target=self._sitzung, args=(roh,), daemon=True).start()

    def _sitzung(self, roh: socket.socket) -> None:
        if self.modus == 'stumm':
            self._halt.wait(120)
            return
        try:
            verbindung = self._server_kontext.wrap_socket(roh, server_side=True)
        except (OSError, ssl.SSLError):
            return
        self._offen.append(verbindung)
        datei = verbindung.makefile('rwb')
        angemeldet = False

        def sende(zeile: str) -> None:
            datei.write(zeile.encode() + b'\r\n')
            datei.flush()

        try:
            sende('* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] IMAP-Attrappe bereit')
            while not self._halt.is_set():
                zeile = datei.readline()
                if not zeile:
                    return
                teile = zeile.decode(errors='replace').strip().split(' ')
                marke, befehl = teile[0], (teile[1].upper() if len(teile) > 1 else '')
                if angemeldet and self.modus == 'stumm_nach_anmeldung' and befehl != 'LOGOUT':
                    self._halt.wait(120)
                    return
                if befehl == 'CAPABILITY':
                    sende('* CAPABILITY IMAP4rev1 AUTH=PLAIN')
                    sende(f'{marke} OK CAPABILITY erledigt')
                elif befehl == 'LOGIN':
                    benutzer = teile[2].strip('"') if len(teile) > 2 else ''
                    passwort = ' '.join(teile[3:]).strip('"') if len(teile) > 3 else ''
                    self.anmeldungen.append((benutzer, passwort))
                    if self.modus == 'imap_aus':
                        sende(f'{marke} NO [ALERT] IMAP access is disabled for this account')
                    elif self.modus == 'google_ablehnen':
                        sende(f'{marke} NO [AUTHENTICATIONFAILED] Invalid credentials (Failure)')
                    elif self.modus == 'ablehnen' or passwort != self.passwort:
                        sende(f'{marke} NO [AUTHENTICATIONFAILED] Authentication failed')
                    else:
                        angemeldet = True
                        sende(f'{marke} OK LOGIN erledigt')
                elif befehl == 'LIST':
                    sende('* LIST (\\HasNoChildren) "/" INBOX')
                    sende(f'{marke} OK LIST erledigt')
                elif befehl in ('SELECT', 'EXAMINE'):
                    self.befehle.append(befehl)
                    # Nur hier, wie bei einem normgerechten Server: UIDVALIDITY und UIDNEXT.
                    sende(f'* {len(self.nachrichten)} EXISTS')
                    sende(f'* OK [UIDVALIDITY {self.uidvalidity}] UIDs gültig')
                    sende(f'* OK [UIDNEXT {len(self.nachrichten) + 1}] Nächste UID')
                    sende(f'{marke} OK [READ-ONLY] {befehl} erledigt')
                elif befehl == 'UID' and len(teile) > 2 and teile[2].upper() == 'FETCH':
                    self.befehle.append('UID FETCH')
                    self._abrufen(marke, teile[3] if len(teile) > 3 else '', ' '.join(teile[4:]), datei, sende)
                elif befehl in ('SEARCH', 'UID'):
                    self.befehle.append('UID SEARCH' if befehl == 'UID' else 'SEARCH')
                    treffer = self._suchen(teile[3:] if befehl == 'UID' else teile[2:])
                    sende('* SEARCH' + ''.join(f' {uid}' for uid in treffer))
                    sende(f'{marke} OK SEARCH erledigt')
                elif befehl == 'NOOP':
                    sende(f'{marke} OK NOOP erledigt')
                elif befehl == 'LOGOUT':
                    sende('* BYE Auf Wiedersehen')
                    sende(f'{marke} OK LOGOUT erledigt')
                    return
                else:
                    sende(f'{marke} BAD unbekannter Befehl')
        except (OSError, ssl.SSLError, ValueError):
            return
        finally:
            try:
                verbindung.close()
            except OSError:
                pass

    def _suchen(self, kriterien: list[str]) -> list[int]:
        """`ALL`, `UNSEEN` und `UID a:b` bzw. `UID a:*`; alles andere wie ALL."""
        alle = list(range(1, len(self.nachrichten) + 1))
        if len(kriterien) >= 2 and kriterien[0].upper() == 'UID':
            von, _, bis = kriterien[1].partition(':')
            unten = int(von)
            oben = len(self.nachrichten) if not bis or bis == '*' else int(bis)
            # Wie RFC 3501: `n:*` liefert mindestens die höchste UID, auch wenn n darüber liegt.
            unten, oben = min(unten, oben), max(unten, oben)
            return [uid for uid in alle if unten <= uid <= oben] or ([alle[-1]] if bis == '*' and alle else [])
        return alle

    def _abrufen(self, marke: str, uids: str, felder: str, datei, sende) -> None:
        """`UID FETCH n (…)` mit UID, FLAGS, RFC822.SIZE und dem Rohtext (auch als Teilabruf `<0.N>`)."""
        teil = re.search(r'<0\.(\d+)>', felder)
        for roh in uids.split(','):
            if not roh.isdigit() or not 1 <= int(roh) <= len(self.nachrichten):
                continue
            uid = int(roh)
            inhalt = self.nachrichten[uid - 1]
            geliefert = inhalt[:int(teil[1])] if teil else inhalt
            name = 'BODY[]<0>' if teil else 'BODY[]'
            kopf = f'* {uid} FETCH (UID {uid} FLAGS () RFC822.SIZE {len(inhalt)} {name} {{{len(geliefert)}}}'
            datei.write(kopf.encode() + b'\r\n' + geliefert + b')\r\n')
            datei.flush()
        sende(f'{marke} OK FETCH erledigt')


__all__ = ['ImapAttrappe', 'PASSWORT', 'probe_mail', 'probe_postfach']
