"""Eine DNS-Attrappe für Tests und Browserproben: beantwortet MX-, CNAME-, TXT- und SRV-Anfragen auf 127.0.0.1 (UDP).

Kein Netz nach außen. Die Einträge gehören synthetischen Domains:

* `praxis-probe.example` liegt bei Google (Google Workspace, MX),
* `firma-probe.example` und `hochschule.example` bei Microsoft 365 (MX auf Exchange Online),
* `filter-probe.example` bei Microsoft 365 hinter einem eigenen Filter (MX eigen, autodiscover-CNAME auf Microsoft),
* `mandant-probe.example` bei Microsoft 365, erkennbar nur am Bestätigungseintrag (TXT `MS=ms…`),
* `eigen-probe.example` bei einem eigenen Server, den nichts verrät (kein SRV, keine Autoconfig, MX unbekannt),
* `verein-probe.example` nennt seinen Mailserver per SRV (RFC 6186: `_imaps._tcp`, `_submission._tcp`),
* `kanzlei-probe.example` sagt per SRV ausdrücklich, dass es kein IMAP und keinen Kalender anbietet (Ziel `.`),
* `verein-probe.example` nennt auch seinen Kalender per SRV (`_caldavs._tcp`, Pfad im TXT-Eintrag),
* `hoster-probe.example` liegt bei IONOS (MX `mx00.ionos.de`), `kas-probe.example` bei ALL-INKL (MX auf einen
  `kasserver.com`-Host, der zugleich der Postfachserver ist).

`srv` (je Instanz) ergänzt oder ersetzt SRV-Einträge, etwa um auf eine IMAP-Attrappe zu zeigen.

Antworten mit Namenskompression wie ein echter Dienst; `stumm` antwortet nie. Wer sie nutzt, setzt
`KINGFISHER_DNS=127.0.0.1:<port>`. `anfragen` sind die gefragten Namen, `fragen` die Paare (Name, Typ).
"""
from __future__ import annotations

import socket
import struct
import threading

MX = {'praxis-probe.example': ['aspmx.l.google.com', 'alt1.aspmx.l.google.com'],
      'firma-probe.example': ['firma-probe-example.mail.protection.outlook.com'],
      'hochschule.example': ['hochschule-example.mail.protection.outlook.com'],
      'filter-probe.example': ['mx.filter-probe.example'],
      'mandant-probe.example': ['mx.mandant-probe.example'],
      'eigen-probe.example': ['mx.eigen-probe.example'],
      'verein-probe.example': ['mx.verein-probe.example'],
      'kanzlei-probe.example': ['mx.kanzlei-probe.example'],
      'hoster-probe.example': ['mx00.ionos.de', 'mx01.ionos.de'],
      'kas-probe.example': ['w0123456.kasserver.com']}
CNAME = {'autodiscover.filter-probe.example': 'autodiscover.outlook.com'}
TXT = {'mandant-probe.example': ['v=spf1 -all', 'MS=ms12345678'],
       '_caldavs._tcp.verein-probe.example': ['path=/dav/'],
       'eigen-probe.example': ['v=spf1 mx -all']}
#: Name -> (Vorrang, Gewicht, Port, Ziel); Ziel `.` heißt „gibt es hier nicht“ (RFC 2782).
SRV = {'_imaps._tcp.verein-probe.example': [(10, 1, 993, 'imap.verein-probe.example'),
                                            (0, 1, 993, 'mail.verein-probe.example')],
       '_submission._tcp.verein-probe.example': [(0, 1, 587, 'mail.verein-probe.example')],
       '_imaps._tcp.kanzlei-probe.example': [(0, 0, 0, '.')],
       '_caldavs._tcp.verein-probe.example': [(0, 1, 443, 'dav.verein-probe.example')],
       '_caldavs._tcp.kanzlei-probe.example': [(0, 0, 0, '.')]}
TYPEN = {5: 'CNAME', 15: 'MX', 16: 'TXT', 33: 'SRV'}


def _name(text: str) -> bytes:
    return b''.join(bytes([len(t)]) + t.encode() for t in text.split('.')) + b'\0'


def _bekannt(domain: str) -> bool:
    return domain in MX or domain in CNAME or domain in TXT or domain in SRV


class Namensdienst:
    """Beantwortet Anfragen aus `MX`, `CNAME`, `TXT`; mit Namenskompression wie ein echter Dienst."""

    def __init__(self, stumm: bool = False, srv: dict[str, list[tuple[int, int, int, str]]] | None = None) -> None:
        self.stumm = stumm
        self.srv = {**SRV, **(srv or {})}
        self.anfragen: list[str] = []
        self.fragen: list[tuple[str, str]] = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1', 0))
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._dienen, daemon=True).start()

    def _antworten(self, domain: str, typ: int) -> list[tuple[int, bytes]]:
        if typ == 15:
            return [(15, struct.pack('>H', vorrang * 10) + _name(host)) for vorrang, host in enumerate(MX.get(domain, []), 1)]
        if typ == 5 and domain in CNAME:
            return [(5, _name(CNAME[domain]))]
        if typ == 16:
            return [(16, bytes([len(text)]) + text.encode()) for text in TXT.get(domain, [])]
        if typ == 33:
            return [(33, struct.pack('>HHH', vorrang, gewicht, port) + (b'\0' if ziel == '.' else _name(ziel)))
                    for vorrang, gewicht, port, ziel in self.srv.get(domain, [])]
        return []

    def _dienen(self) -> None:
        while True:
            try:
                paket, absender = self.sock.recvfrom(512)
            except OSError:
                return
            kennung, = struct.unpack('>H', paket[:2])
            stelle, teile = 12, []
            while paket[stelle]:
                teile.append(paket[stelle + 1:stelle + 1 + paket[stelle]].decode())
                stelle += 1 + paket[stelle]
            typ, = struct.unpack('>H', paket[stelle + 1:stelle + 3])
            frage = paket[12:stelle + 5]
            domain = '.'.join(teile)
            self.anfragen.append(domain)
            self.fragen.append((domain, TYPEN.get(typ, str(typ))))
            if self.stumm:
                continue
            eintraege = self._antworten(domain, typ)
            antworten = b''
            for art, daten in eintraege:
                # 0xC00C zeigt auf den Namen der Frage (Kompression).
                antworten += struct.pack('>HHHIH', 0xC00C, art, 1, 300, len(daten)) + daten
            kopf = struct.pack('>HHHHHH', kennung, 0x8180 if eintraege or _bekannt(domain) or domain in self.srv else 0x8183, 1,
                               len(eintraege), 0, 0)
            self.sock.sendto(kopf + frage + antworten, absender)

    def schliessen(self) -> None:
        self.sock.close()


__all__ = ["CNAME", "MX", "SRV", "TXT", "Namensdienst"]
