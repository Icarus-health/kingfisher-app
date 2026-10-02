"""Das Logbuch: eine anhängende Chronik dessen, was Kingfisher getan hat, und drei Zeilen daraus fürs Briefing.

Morgens soll ein Blick genügen: „Seit gestern Abend: 41 Mails aufgenommen, 2 neue Akten (Anna Keller,
Projekt Mainz).“ Ohne Fachwörter, ohne Zahlenfriedhof. Dieses Modul hat zwei Hälften.

**Die Chronik.** Eine eigene kleine Datei, `logbuch.sqlite3` (Tabelle `ereignis`, eigene Versionierung),
in der Sicherung wie `rueckmeldungen.sqlite3`. Einträge werden nie geändert und nie gelöscht; zwei Trigger
verhindern das auf Datenbankebene (wie beim Audit-Log). Ein Eintrag hat einen Zeitpunkt, eine Art
(`ARTEN`) und Nutzdaten. **Kein Rohtext**: Mails, Notizen und Antworten stehen hier nie, nur Zähler,
Titel von Sachen, Kennungen und kurze Stichworte. Die Nutzdaten werden beim Schreiben gekürzt, und Felder
mit Namen wie `text` oder `body` fallen weg (`_bereinigen`).

Schreibende Stellen rufen `logbuch.vermerke(art, **daten)`. Der Aufruf ist **nie** ein Grund, dass eine
Aktion scheitert: Jeder Fehler wird geschluckt und geloggt, auch ein fehlendes oder geschlossenes Logbuch.
Darum ist `vermerke` auf Modulebene eine Funktion über das „aktive“ Logbuch (`verbinde`), nicht eine
Methode, die jede Stelle erst beschaffen müsste.

Die Art-spezifischen Nutzdaten (`sorte` ist die Unterart; das Schlüsselwort `art` ist die Art des Eintrags):

| Art | Nutzdaten |
|---|---|
| `quellen` | `sorte` (`mail`, `dokument`, `gespraech`, `termin`, `notiz`, sonst), `anzahl` |
| `akte_neu`, `akte_aktualisiert` | `sache` (Kennung), `name` (Titel der Sache) |
| `vorschlag_erzeugt`, `vorschlag_angenommen`, `vorschlag_abgelehnt` | `sorte` (Art des Vorschlags), `id` |
| `lint` | `befunde`: Anzahl je Art, z. B. `{'widerspruch': 1}` |
| `fehler` | `was` (Name des Schritts der Hintergrundarbeit, nie der Fehlertext) |
| `modellwechsel` | `rolle`, `wofuer` (Alltagsname der Rolle), `lokal` |
| `export` | `was` |
| `rueckmeldung` | `sorte` |
| `zu_lang` | `sorte`, `anzahl`: Quellen über der Obergrenze der Einordnung (`abschnitte.OBERGRENZE`), nicht eingeordnet |

**Die Zusammenfassung.** `seit(zeitpunkt)` zählt die Einträge seit dem Zeitpunkt, `drei_zeilen` macht daraus
höchstens drei Zeilen Alltagssprache: erst was hereinkam (Quellen, Akten), dann was dein Auge braucht
(Befunde, Vorschläge), zuletzt der Betrieb (Fehler, Modellwechsel, Exporte, Rückmeldungen). Leere
Kategorien fehlen; ist nichts geschehen, steht da „Nichts Neues seit gestern Abend.“

**Seit dem letzten Blick.** Bezugspunkt ist der letzte Aufruf des Briefings, gespeichert in der Tabelle
`marke`. Damit ein Neuladen die Zeilen nicht leert, gilt eine Sitzung: Liegt der vorige Aufruf weniger als
`SITZUNG_LUECKE` zurück, bleibt der Bezugspunkt der Beginn dieser Sitzung (der letzte Aufruf davor).
Erst nach einer Pause rückt er auf den letzten Aufruf vor der Pause. Ohne gespeicherten Aufruf gelten
24 Stunden (`bezugspunkt`).

**Lint.** Ein anderer Baustein prüft die Akten und liefert `lint.zusammenfassung()`. Das Logbuch bindet
es über den optionalen `befunde_lieferant` ein (ein Aufruf ohne Argumente, der `{Art: Anzahl}` liefert).
Fehlt er oder wirft er, fehlt die Zeile; das Logbuch hängt von Lint nicht ab. Wer selbst die Funde eines Laufs
festhält (`vermerke('lint', befunde={...})`), bestimmt die Zeile („gefunden“). Gibt es keinen solchen Eintrag im
Zeitraum, zeigt der Lieferant den **heutigen Stand** („noch offen“), weil ein Stand kein „seit“ kennt.

Ohne Modell, deterministisch, nachprüfbar.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any

from .datumstext import MONATE, iso_versuchen_utc
from .migrations import Migration, run_migrations, verify_schema

logger = logging.getLogger(__name__)

ARTEN = ('quellen', 'akte_neu', 'akte_aktualisiert', 'vorschlag_erzeugt', 'vorschlag_angenommen',
         'vorschlag_abgelehnt', 'lint', 'fehler', 'modellwechsel', 'export', 'rueckmeldung', 'zu_lang')

#: Liegt der vorige Blick weniger weit zurück, gehört der neue zur selben Sitzung (siehe Modulkopf).
SITZUNG_LUECKE = timedelta(hours=3)
#: Ohne gespeicherten Blick zählt so weit zurück.
STANDARD_RUECKBLICK = timedelta(hours=24)
#: Weiter als das schaut das Briefing nie zurück (die Chronik selbst bleibt).
MAX_RUECKBLICK = timedelta(days=30)
#: Obergrenze der Einträge je Abfrage; `seit` zählt, statt Listen zu laden.
MAX_EREIGNISSE = 50000

MAX_ZEICHEN = 120
MAX_ELEMENTE = 20
#: Nutzdaten mit diesen Namen werden nie gespeichert: Das Logbuch kennt keinen Rohtext.
VERBOTENE_FELDER = frozenset({'text', 'body', 'inhalt', 'betreff', 'absender', 'empfaenger', 'adresse', 'rohtext',
                              'antwort', 'frage', 'detail', 'fehlertext', 'nachricht', 'snippet', 'zitat'})

_TABELLEN = {'ereignis': {'id', 'zeit', 'art', 'daten'}, 'marke': {'name', 'wert'}}
_SCHLUESSEL = {'ereignis': {'id'}, 'marke': {'name'}}

_TRIGGER_UPDATE = """
CREATE TRIGGER IF NOT EXISTS ereignis_no_update
BEFORE UPDATE ON ereignis
BEGIN
    SELECT RAISE(ABORT, 'Logbuch ist anhaengend: UPDATE nicht erlaubt');
END;
"""
_TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS ereignis_no_delete
BEFORE DELETE ON ereignis
BEGIN
    SELECT RAISE(ABORT, 'Logbuch ist anhaengend: DELETE nicht erlaubt');
END;
"""
_TRIGGER = {'ereignis_no_update': _TRIGGER_UPDATE, 'ereignis_no_delete': _TRIGGER_DELETE}


def _migrieren(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE ereignis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zeit REAL NOT NULL,
        art TEXT NOT NULL,
        daten TEXT NOT NULL DEFAULT '{}')""")
    conn.execute('CREATE INDEX idx_ereignis_zeit ON ereignis(zeit)')
    conn.execute('CREATE TABLE marke (name TEXT PRIMARY KEY, wert TEXT NOT NULL)')
    conn.execute(_TRIGGER_UPDATE)
    conn.execute(_TRIGGER_DELETE)


def _pruefen(conn: sqlite3.Connection) -> None:
    from .migrations import IndexContract
    verify_schema(conn, expected_tables=_TABELLEN, expected_primary_keys=_SCHLUESSEL,
                  expected_indexes={'idx_ereignis_zeit': IndexContract('ereignis', ('zeit',))},
                  expected_triggers=_TRIGGER)


_MIGRATIONS = (Migration(1, 'logbuch', _migrieren, _pruefen),)


# -- Bereinigen ------------------------------------------------------------------------------------


def _skalar(wert: Any) -> Any:
    if wert is None or isinstance(wert, (bool, int, float)):
        return wert
    return ' '.join(str(wert).split())[:MAX_ZEICHEN]


def _bereinigen(daten: dict[str, Any]) -> dict[str, Any]:
    """Nur kurze, flache Nutzdaten; Felder, die nach Rohtext aussehen, fallen weg."""
    sauber: dict[str, Any] = {}
    for schluessel, wert in daten.items():
        name = str(schluessel)[:40]
        if name.lower() in VERBOTENE_FELDER:
            continue
        if isinstance(wert, dict):
            sauber[name] = {str(k)[:MAX_ZEICHEN]: _skalar(v) for k, v in list(wert.items())[:MAX_ELEMENTE]}
        elif isinstance(wert, (list, tuple, set, frozenset)):
            sauber[name] = [_skalar(v) for v in list(wert)[:MAX_ELEMENTE]]
        else:
            sauber[name] = _skalar(wert)
    return sauber


# -- Die Zusammenfassung ----------------------------------------------------------------------------


@dataclass
class Ereignis:
    id: int
    zeit: datetime
    art: str
    daten: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {'id': self.id, 'zeit': self.zeit.isoformat(timespec='seconds'), 'art': self.art, 'daten': self.daten}


@dataclass
class Zusammenfassung:
    """Was in einem Zeitraum geschah, gezählt. Kein Text; den macht `drei_zeilen`."""

    seit: datetime
    bis: datetime
    quellen: dict[str, int] = field(default_factory=dict)
    akten_neu: list[dict[str, str]] = field(default_factory=list)
    akten_aktualisiert: list[dict[str, str]] = field(default_factory=list)
    vorschlaege_erzeugt: int = 0
    vorschlaege_angenommen: int = 0
    vorschlaege_abgelehnt: int = 0
    befunde: dict[str, int] = field(default_factory=dict)
    befunde_quelle: str = ''
    """`ereignisse` (in diesem Zeitraum gefunden) oder `lieferant` (heutiger Stand, noch offen); leer ohne Befunde."""
    fehler: list[str] = field(default_factory=list)
    modellwechsel: list[str] = field(default_factory=list)
    exporte: int = 0
    rueckmeldungen: int = 0
    seit_beginn: bool = False
    """Der Zeitraum beginnt erst mit dem Logbuch (es ist jünger als der gefragte Rückblick): davor gab es nichts."""
    zu_lang: int = 0
    """Quellen, die für die Einordnung zu lang waren (über `abschnitte.OBERGRENZE`)."""

    @property
    def leer(self) -> bool:
        return not (self.quellen or self.akten_neu or self.akten_aktualisiert or self.vorschlaege_erzeugt
                    or self.vorschlaege_angenommen or self.vorschlaege_abgelehnt or self.befunde or self.fehler
                    or self.modellwechsel or self.exporte or self.rueckmeldungen or self.zu_lang)

    def to_dict(self) -> dict[str, Any]:
        return {'seit': self.seit.isoformat(timespec='seconds'), 'bis': self.bis.isoformat(timespec='seconds'),
                'quellen': self.quellen, 'akten_neu': self.akten_neu, 'akten_aktualisiert': self.akten_aktualisiert,
                'vorschlaege': {'erzeugt': self.vorschlaege_erzeugt, 'angenommen': self.vorschlaege_angenommen,
                                'abgelehnt': self.vorschlaege_abgelehnt},
                'befunde': self.befunde, 'befunde_quelle': self.befunde_quelle, 'fehler': self.fehler,
                'modellwechsel': self.modellwechsel, 'exporte': self.exporte, 'rueckmeldungen': self.rueckmeldungen,
                'zu_lang': self.zu_lang}


def _anzahl(wert: Any, vorgabe: int = 1) -> int:
    if isinstance(wert, bool):
        return vorgabe
    try:
        zahl = int(wert)
    except (TypeError, ValueError):
        return vorgabe
    return max(0, min(zahl, 10_000_000))


def _befunde_flach(roh: Any) -> dict[str, int]:
    """Anzahl je Art aus dem, was der Lieferant gibt. Gesamtsummen zählen nicht doppelt; Unbrauchbares fällt weg."""
    if not isinstance(roh, dict):
        return {}
    ergebnis: dict[str, int] = {}
    for schluessel, wert in roh.items():
        name = str(schluessel)
        if name in ('gesamt', 'insgesamt', 'summe', 'total', 'anzahl'):
            continue
        if isinstance(wert, dict) and name in ('je_art', 'nach_art', 'arten', 'befunde'):
            for art, anzahl in _befunde_flach(wert).items():
                ergebnis[art] = ergebnis.get(art, 0) + anzahl
        elif isinstance(wert, (int, float)) and not isinstance(wert, bool) and wert > 0:
            ergebnis[name] = ergebnis.get(name, 0) + int(wert)
    return ergebnis


def zusammenfassen(ereignisse: Iterable[Ereignis], seit: datetime, bis: datetime) -> Zusammenfassung:
    """Zählt Einträge zu einer Zusammenfassung. Rein; ohne Datenbank und ohne Lint."""
    z = Zusammenfassung(seit=seit, bis=bis)
    neu: dict[str, dict[str, str]] = {}
    geaendert: dict[str, dict[str, str]] = {}
    fehler: Counter[str] = Counter()
    gefunden: Counter[str] = Counter()
    for e in ereignisse:
        d = e.daten
        if e.art == 'quellen':
            n = _anzahl(d.get('anzahl'))
            if n:
                sorte = str(d.get('sorte') or 'sonstige')
                z.quellen[sorte] = z.quellen.get(sorte, 0) + n
        elif e.art in ('akte_neu', 'akte_aktualisiert'):
            sache = str(d.get('sache') or d.get('name') or '')
            if sache:
                ziel = neu if e.art == 'akte_neu' else geaendert
                ziel.setdefault(sache, {'sache': sache, 'name': str(d.get('name') or sache)})
        elif e.art == 'vorschlag_erzeugt':
            z.vorschlaege_erzeugt += _anzahl(d.get('anzahl'))
        elif e.art == 'vorschlag_angenommen':
            z.vorschlaege_angenommen += _anzahl(d.get('anzahl'))
        elif e.art == 'vorschlag_abgelehnt':
            z.vorschlaege_abgelehnt += _anzahl(d.get('anzahl'))
        elif e.art == 'lint':
            gefunden.update(_befunde_flach(d.get('befunde')))
        elif e.art == 'fehler':
            fehler[str(d.get('was') or '')] += 1
        elif e.art == 'modellwechsel':
            z.modellwechsel.append(str(d.get('wofuer') or d.get('rolle') or ''))
        elif e.art == 'export':
            z.exporte += 1
        elif e.art == 'rueckmeldung':
            z.rueckmeldungen += 1
        elif e.art == 'zu_lang':
            z.zu_lang += _anzahl(d.get('anzahl'))
    z.akten_neu = list(neu.values())
    # Eine Akte, die in diesem Zeitraum entstand, gilt nicht zusätzlich als ergänzt.
    z.akten_aktualisiert = [a for k, a in geaendert.items() if k not in neu]
    z.befunde = {k: v for k, v in gefunden.items() if v > 0}
    z.befunde_quelle = 'ereignisse' if z.befunde else ''
    z.fehler = [was for was, n in fehler.items() for _ in range(n)]
    return z


# -- Die Wörter ------------------------------------------------------------------------------------

_QUELLEN_WORT = {'mail': ('Mail', 'Mails'), 'dokument': ('Dokument', 'Dokumente'), 'gespraech': ('Gespräch', 'Gespräche'),
                 'termin': ('Termin', 'Termine'), 'notiz': ('Notiz', 'Notizen'), 'sonstige': ('Quelle', 'Quellen')}
_BEFUND_WORT = {'widerspruch': ('Widerspruch', 'Widersprüche'), 'veraltet': ('veraltete Angabe', 'veraltete Angaben'),
                'ohne_akte': ('Sache ohne Akte', 'Sachen ohne Akte'),
                'ohne_quellen': ('Akte ohne neue Quellen', 'Akten ohne neue Quellen'),
                'querverweis': ('fehlender Querverweis', 'fehlende Querverweise'),
                'sonstige': ('Auffälligkeit', 'Auffälligkeiten')}
#: Was im Hintergrund lief, so wie man es sagen würde (Fremdprobe 2, Befund 15: nicht „Verdichtung“, nicht „gehakt“).
_SCHRITT_WORT = {'aufnahme': 'Quellen aufnehmen', 'gedaechtnis': 'Quellen einordnen', 'lage': 'Lagebilder',
                 'zusagen': 'Zusagen erkennen', 'verdichtung': 'Wissensvorschläge', 'zusammenfassung': 'Zusammenfassungen',
                 'sicherung': 'Sicherung', 'mailabruf': 'Mails abrufen'}
#: Wo der Mensch selbst nachsehen sollte, wenn es dabei bleibt; bei allen anderen Schritten muss er nichts tun.
_SCHRITT_TUN = {'sicherung': 'bleibt es dabei, sieh unter Einstellungen → Sicherung nach',
                'mailabruf': 'bleibt es dabei, prüfe dein Postfach unter Einstellungen → Zugänge'}
_AKTEN_VORSILBE = {'projekt': 'Projekt ', 'thema': 'Thema '}
MAX_NAMEN = 3
MAX_NAME = 40


def _zahl(n: int, einzahl: str, mehrzahl: str) -> str:
    return f'{n} {einzahl if n == 1 else mehrzahl}'


def _aufzaehlung(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else ', '.join(teile[:-1]) + ' und ' + teile[-1]


def _kurz(text: str, laenge: int = MAX_NAME) -> str:
    text = ' '.join(str(text).split())
    return text if len(text) <= laenge else text[:laenge].rsplit(' ', 1)[0].rstrip(',;:.') + ' …'


def _aktenname(akte: dict[str, str]) -> str:
    art = akte.get('sache', '').split(':', 1)[0]
    name = _kurz(akte.get('name') or akte.get('sache') or '')
    vorsilbe = _AKTEN_VORSILBE.get(art, '')
    return name if not vorsilbe or name.lower().startswith(vorsilbe.lower()) else vorsilbe + name


def _namen(akten: list[dict[str, str]]) -> str:
    namen = [_aktenname(a) for a in akten[:MAX_NAMEN]]
    rest = len(akten) - len(namen)
    return ', '.join(namen) + (f' und {rest} weitere' if rest > 0 else '')


def _quellen_satz(z: Zusammenfassung) -> str:
    teile = []
    for sorte, n in sorted(z.quellen.items(), key=lambda p: (-p[1], p[0])):
        einzahl, mehrzahl = _QUELLEN_WORT.get(sorte, _QUELLEN_WORT['sonstige'])
        teile.append(_zahl(n, einzahl, mehrzahl))
    return f'{_aufzaehlung(teile)} aufgenommen' if teile else ''


def _akten_saetze(z: Zusammenfassung) -> list[str]:
    saetze = []
    if z.akten_neu:
        saetze.append(f'{_zahl(len(z.akten_neu), "neue Akte", "neue Akten")} ({_namen(z.akten_neu)})')
    if z.akten_aktualisiert:
        n = len(z.akten_aktualisiert)
        saetze.append(f'{_zahl(n, "Akte", "Akten")} ergänzt' + (f' ({_namen(z.akten_aktualisiert)})' if n <= MAX_NAMEN and not z.akten_neu else ''))
    return saetze


def _befund_satz(z: Zusammenfassung) -> str:
    if not z.befunde:
        return ''
    teile = []
    for art, n in sorted(z.befunde.items(), key=lambda p: (-p[1], p[0]))[:MAX_NAMEN]:
        einzahl, mehrzahl = _BEFUND_WORT.get(art, _BEFUND_WORT['sonstige'])
        teile.append(_zahl(n, einzahl, mehrzahl))
    rest = len(z.befunde) - len(teile)
    if rest > 0:
        teile.append(f'{rest} weitere Hinweise')
    return f'{_aufzaehlung(teile)} {"gefunden" if z.befunde_quelle == "ereignisse" else "noch offen"}'


def _vorschlag_saetze(z: Zusammenfassung) -> list[str]:
    saetze = []
    if z.vorschlaege_erzeugt:
        saetze.append(_zahl(z.vorschlaege_erzeugt, 'neuer Vorschlag', 'neue Vorschläge'))
    if z.vorschlaege_angenommen:
        saetze.append(f'{_zahl(z.vorschlaege_angenommen, "Vorschlag", "Vorschläge")} angenommen')
    if z.vorschlaege_abgelehnt:
        saetze.append(f'{_zahl(z.vorschlaege_abgelehnt, "Vorschlag", "Vorschläge")} abgelehnt')
    return saetze


def _schritt(was: str) -> str:
    """Der Schritt hinter dem Namen eines Laufs; ein Postfach (`mail:<konto>`) ist „Mails abrufen“."""
    return 'mailabruf' if was.startswith('mail:') else was


def fehler_satz(fehler: list[str]) -> str:
    """Was im Hintergrund nicht fertig wurde, in Alltagssprache, und ob der Mensch etwas tun muss.

    Meist muss er nichts tun: Der nächste Lauf versucht es von selbst. Nur wo ein Mensch helfen kann (Postfach,
    Sicherung), steht, wo er nachsieht. Zwei Sätze in einem Stück; `drei_zeilen` stellt es ans Ende seiner Zeile.
    """
    schritte = list(dict.fromkeys(_schritt(w) for w in fehler))
    namen = [_SCHRITT_WORT.get(w, 'Hintergrundarbeit') for w in schritte]
    mal = 'einmal' if len(fehler) == 1 else f'{len(fehler)}-mal'
    tun = [_SCHRITT_TUN[w] for w in schritte if w in _SCHRITT_TUN]
    weiter = ('Kingfisher versucht es von selbst noch einmal; ' + '; '.join(tun) if tun
              else 'Du musst nichts tun: Kingfisher versucht es von selbst noch einmal')
    return (f'Im Hintergrund ist {mal} etwas nicht fertig geworden '
            f'({_aufzaehlung(list(dict.fromkeys(namen))[:MAX_NAMEN])}). {weiter}')


def _betriebs_saetze(z: Zusammenfassung) -> list[str]:
    saetze = []
    if z.fehler:
        saetze.append(fehler_satz(z.fehler))
    if z.modellwechsel:
        wofuer = list(dict.fromkeys(w for w in z.modellwechsel if w))
        saetze.append(f'{_zahl(len(z.modellwechsel), "Modell", "Modelle")} gewechselt'
                      + (f' ({_aufzaehlung([_kurz(w, 30) for w in wofuer[:MAX_NAMEN]])})' if wofuer else ''))
    if z.exporte:
        saetze.append(f'{_zahl(z.exporte, "Export", "Exporte")} angelegt')
    if z.rueckmeldungen:
        saetze.append(f'{_zahl(z.rueckmeldungen, "Rückmeldung", "Rückmeldungen")} „Stimmt nicht“ notiert')
    if z.zu_lang:
        saetze.append(f'{_zahl(z.zu_lang, "Quelle", "Quellen")} zu lang zum Einordnen')
    return saetze


def gruppen(z: Zusammenfassung) -> dict[str, list[str]]:
    """Die Aussagen der Zusammenfassung in drei Gruppen, je Aussage ein kurzes Satzstück ohne Punkt.

    `hereingekommen` (Quellen, Akten), `pruefen` (Befunde, Vorschläge), `betrieb` (Fehler, Modelle, Exporte, Rückmeldungen).
    Leere Aussagen fehlen; leere Gruppen bleiben als leere Liste stehen.
    """
    return {'hereingekommen': [s for s in (_quellen_satz(z), *_akten_saetze(z)) if s],
            'pruefen': [s for s in (_befund_satz(z), *_vorschlag_saetze(z)) if s],
            'betrieb': _betriebs_saetze(z)}


def _tagesteil(stunde: int) -> str:
    return 'Nacht' if stunde < 5 else 'früh' if stunde < 11 else 'Mittag' if stunde < 14 else 'Nachmittag' if stunde < 18 else 'Abend'


_WOCHENTAGE = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')


def seit_text(seit: datetime, jetzt: datetime) -> str:
    """„gestern Abend“, „heute früh“, „Montag“: so, wie man den Bezugspunkt sagen würde (in der Zone von `jetzt`)."""
    seit = seit.astimezone(jetzt.tzinfo) if jetzt.tzinfo else seit
    tage = (jetzt.date() - seit.date()).days
    if jetzt - seit < timedelta(hours=2):
        return 'kurzem'
    if tage <= 0:
        return f'heute {_tagesteil(seit.hour)}'
    if tage == 1:
        return f'gestern {_tagesteil(seit.hour)}'
    if tage == 2:
        return 'vorgestern'
    if tage < 7:
        return _WOCHENTAGE[seit.weekday()]
    return f'dem {seit.day}. {MONATE[seit.month - 1]}'


def _satz(teile: list[str]) -> str:
    return ', '.join(teile) + '.'


def _zeile(gruppe: str, teile: list[str], z: Zusammenfassung) -> str:
    """Eine Zeile der Zusammenfassung. Im Betrieb steht der Satz zu dem, was nicht fertig wurde, als eigener Satz am Ende."""
    if gruppe == 'betrieb' and z.fehler:
        fehler, rest = teile[0], teile[1:]
        return (f'{_satz(rest)} ' if rest else '') + fehler + '.'
    return _satz(teile)


def _heute_begonnen(z: Zusammenfassung) -> bool:
    """Wahr, wenn das Logbuch erst heute angelegt wurde: Dann gab es kein „gestern Abend“ (Fremdprobe, Befund 29)."""
    if not z.seit_beginn:
        return False
    seit = z.seit.astimezone(z.bis.tzinfo) if z.bis.tzinfo else z.seit
    return seit.date() == z.bis.date()


def drei_zeilen(z: Zusammenfassung) -> list[str]:
    """Höchstens drei Zeilen Alltagssprache. Die erste beginnt mit „Seit gestern Abend:“. Nichts Neues: ein Satz.

    Am Tag, an dem das Logbuch angelegt wurde (am Tag der Einrichtung), heißt es „Heute:“ statt „Seit gestern Abend:“.
    """
    heute = _heute_begonnen(z)
    bezug = seit_text(z.seit, z.bis)
    if z.leer:
        return ['Heute noch nichts Neues.'] if heute else [f'Nichts Neues seit {bezug}.']
    zeilen = [_zeile(name, teile, z) for name, teile in gruppen(z).items() if teile]
    zeilen[0] = f'Heute: {zeilen[0]}' if heute else f'Seit {bezug}: {zeilen[0]}'
    return zeilen[:3]


# -- Die Chronik -----------------------------------------------------------------------------------


def _als_zeit(wert: datetime | float | int) -> float:
    if isinstance(wert, datetime):
        return (wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)).timestamp()
    return float(wert)


def _utc(zeit: float) -> datetime:
    return datetime.fromtimestamp(zeit, timezone.utc)


class Logbuch:
    """Die Chronik in ihrer eigenen Datei."""

    def __init__(self, path: str | Path, *, uhr: Callable[[], float] = time.time,
                 befunde_lieferant: Callable[[], dict] | None = None) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._uhr = uhr
        self.befunde_lieferant = befunde_lieferant
        self._lock = threading.RLock()
        self._zu = False
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            run_migrations(self._conn, store='logbuch', path=self._path, migrations=_MIGRATIONS)
            with self._lock:
                if self._marke('angelegt') is None:
                    self._marke_setzen('angelegt', self._uhr())
                    self._conn.commit()
        except Exception:
            self._conn.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._zu = True
            self._conn.close()

    # -- Schreiben --

    def vermerke(self, art: str, **daten: Any) -> bool:
        """Hängt einen Eintrag an. Wirft nie; `False`, wenn nichts geschrieben wurde (und warum steht im Log)."""
        try:
            if art not in ARTEN:
                logger.warning('Logbuch: unbekannte Art %r ignoriert', art)
                return False
            with self._lock:
                if self._zu:
                    return False
                self._conn.execute('INSERT INTO ereignis(zeit, art, daten) VALUES (?,?,?)',
                                   (self._uhr(), art, json.dumps(_bereinigen(daten), ensure_ascii=False)))
                self._conn.commit()
            return True
        except Exception:  # noqa: BLE001 - das Logbuch darf nie eine Aktion scheitern lassen
            logger.exception('Logbuch: Eintrag %r konnte nicht geschrieben werden', art)
            return False

    # -- Lesen --

    def ereignisse(self, von: datetime | float, bis: datetime | float | None = None, *,
                   limit: int = MAX_EREIGNISSE) -> list[Ereignis]:
        """Einträge von `von` (einschließlich) bis `bis` (ausschließlich), älteste zuerst."""
        ende = _als_zeit(bis) if bis is not None else float('inf')
        with self._lock:
            zeilen = self._conn.execute('SELECT id, zeit, art, daten FROM ereignis WHERE zeit >= ? AND zeit < ? '
                                        'ORDER BY zeit, id LIMIT ?', (_als_zeit(von), ende, limit)).fetchall()
        ergebnis = []
        for z in zeilen:
            try:
                daten = json.loads(z['daten'])
            except ValueError:
                daten = {}
            ergebnis.append(Ereignis(z['id'], _utc(z['zeit']), z['art'], daten if isinstance(daten, dict) else {}))
        return ergebnis

    def zaehlen(self) -> int:
        with self._lock:
            return int(self._conn.execute('SELECT COUNT(*) FROM ereignis').fetchone()[0])

    def seit(self, zeitpunkt: datetime, bis: datetime | None = None) -> Zusammenfassung:
        """Was seit `zeitpunkt` geschah. Zeitpunkt und Ende behalten ihre Zone (für „gestern Abend“)."""
        if zeitpunkt.tzinfo is None:
            zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
        # Vor dem Anlegen des Logbuchs gab es nichts zu vermerken: Der Zeitraum beginnt dann dort, nicht „gestern Abend“.
        with self._lock:
            angelegt = None if self._zu else self._marke('angelegt')
        beginn = isinstance(angelegt, (int, float)) and _utc(angelegt) > zeitpunkt
        if beginn:
            zeitpunkt = _utc(angelegt).astimezone(zeitpunkt.tzinfo)
        # Ohne Ende zählt alles bis jetzt mit; mit Ende gilt es ausschließlich, damit kein Eintrag in zwei Zeiträume fällt.
        z = zusammenfassen(self.ereignisse(zeitpunkt, bis), zeitpunkt, bis or _utc(self._uhr()).astimezone(zeitpunkt.tzinfo))
        z.seit_beginn = beginn
        if not z.befunde and self.befunde_lieferant is not None:
            try:
                z.befunde = _befunde_flach(self.befunde_lieferant())
                z.befunde_quelle = 'lieferant' if z.befunde else ''
            except Exception:  # noqa: BLE001 - Lint ist Beiwerk; ohne ihn fehlt nur die Zeile
                logger.exception('Logbuch: Befunde konnten nicht geholt werden')
        return z

    def tage(self, von: datetime, bis: datetime, zone: tzinfo | None = None) -> list[dict[str, Any]]:
        """Die Chronik nach Tagen gruppiert (jüngster zuerst), je Tag die Aussagen in Alltagssprache.

        Tage ohne Aussage fehlen. Der Lieferant bleibt außen vor: Die Chronik zeigt Geschehenes, keinen Stand.
        """
        zone = zone or bis.tzinfo or timezone.utc
        nach_tag: dict[Any, list[Ereignis]] = {}
        for e in self.ereignisse(von, bis):
            nach_tag.setdefault(e.zeit.astimezone(zone).date(), []).append(e)
        heute = bis.astimezone(zone).date()
        tage = []
        for tag in sorted(nach_tag, reverse=True):
            tagesbeginn = datetime(tag.year, tag.month, tag.day, tzinfo=zone)
            z = zusammenfassen(nach_tag[tag], tagesbeginn, tagesbeginn + timedelta(days=1))
            eintraege = [s[0].upper() + s[1:] for teile in gruppen(z).values() for s in teile]
            if eintraege:
                tage.append({'tag': tag.isoformat(), 'titel': _tagestitel(tag, heute), 'eintraege': eintraege})
        return tage

    # -- Der letzte Blick --

    def _marke(self, name: str) -> Any:
        zeile = self._conn.execute('SELECT wert FROM marke WHERE name = ?', (name,)).fetchone()
        if zeile is None:
            return None
        try:
            return json.loads(zeile['wert'])
        except ValueError:
            return None

    def _marke_setzen(self, name: str, wert: Any) -> None:
        self._conn.execute('INSERT INTO marke(name, wert) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET wert = excluded.wert',
                           (name, json.dumps(wert, ensure_ascii=False)))

    def bezugspunkt(self, jetzt: datetime, *, buchen: bool = True) -> datetime:
        """Ab wann „seit dem letzten Blick“ gilt, und (mit `buchen`) dieser Aufruf als neuer Blick.

        Sitzungsregel siehe Modulkopf. Ohne gespeicherten Blick: 24 Stunden. Nie weiter zurück als `MAX_RUECKBLICK`.
        Wirft nie; im Zweifel 24 Stunden.
        """
        if jetzt.tzinfo is None:
            jetzt = jetzt.replace(tzinfo=timezone.utc)
        standard = jetzt - STANDARD_RUECKBLICK
        try:
            with self._lock:
                if self._zu:
                    return standard
                blick, vorher = self._marke('blick'), self._marke('vorher')
                jetzt_s = jetzt.timestamp()
                if isinstance(blick, (int, float)) and jetzt_s - blick > SITZUNG_LUECKE.total_seconds():
                    vorher = blick
                elif not isinstance(blick, (int, float)):
                    vorher = None
                if buchen:
                    self._marke_setzen('vorher', vorher)
                    self._marke_setzen('blick', jetzt_s)
                    self._conn.commit()
                bezug = _utc(vorher).astimezone(jetzt.tzinfo) if isinstance(vorher, (int, float)) else standard
        except Exception:  # noqa: BLE001
            logger.exception('Logbuch: der letzte Blick konnte nicht bestimmt werden')
            return standard
        return max(bezug, jetzt - MAX_RUECKBLICK)

    # -- Akten abgleichen --

    def akten_abgleichen(self, sachen: Iterable[dict[str, Any]]) -> int:
        """Vergleicht die Sachen mit dem zuletzt gesehenen Stand und vermerkt neue und veränderte Akten.

        `sachen`: je Sache `sache` (Kennung), `name`, `letzte` (letzte Aktivität als Text). Der allererste Abgleich
        hat keinen Stand: Was schon vor dem Logbuch da war (letzte Aktivität vor dessen Anlegen), ist nicht „neu“
        und setzt nur den Stand. Danach gilt jede unbekannte Sache als neu, auch nach einem leeren Stand.
        Wirft nie; gibt die Zahl der Einträge zurück.
        """
        try:
            aktuell = {str(s['sache']): (str(s.get('name') or s['sache']), str(s.get('letzte') or '')) for s in sachen}
            with self._lock:
                if self._zu:
                    return 0
                bekannt = self._marke('akten')
                geschrieben = 0
                if isinstance(bekannt, dict):
                    for sache, (name, letzte) in aktuell.items():
                        if sache not in bekannt:
                            geschrieben += self.vermerke('akte_neu', sache=sache, name=name)
                        elif letzte and letzte != bekannt[sache]:
                            geschrieben += self.vermerke('akte_aktualisiert', sache=sache, name=name)
                else:
                    angelegt = self._marke('angelegt')
                    for sache, (name, letzte) in aktuell.items():
                        if isinstance(angelegt, (int, float)) and _zeit_aus_text(letzte) >= angelegt:
                            geschrieben += self.vermerke('akte_neu', sache=sache, name=name)
                # Sachen, die nur in dieser Stichprobe fehlen (z. B. über der Obergrenze), bleiben im Stand.
                stand = dict(bekannt) if isinstance(bekannt, dict) else {}
                stand.update({sache: letzte for sache, (_, letzte) in aktuell.items()})
                self._marke_setzen('akten', stand)
                self._conn.commit()
                return geschrieben
        except Exception:  # noqa: BLE001
            logger.exception('Logbuch: Akten konnten nicht abgeglichen werden')
            return 0


def _zeit_aus_text(text: str) -> float:
    """Zeitpunkt eines ISO-Textes (ohne Zone: UTC); unlesbar oder leer zählt als uralt."""
    zeit = iso_versuchen_utc(text)
    return zeit.timestamp() if zeit is not None else float('-inf')


def _tagestitel(tag: Any, heute: Any) -> str:
    abstand = (heute - tag).days
    if abstand == 0:
        return 'Heute'
    if abstand == 1:
        return 'Gestern'
    if abstand == 2:
        return 'Vorgestern'
    return f'{_WOCHENTAGE[tag.weekday()]}, {tag.day}. {MONATE[tag.month - 1]}'


# -- Das aktive Logbuch ----------------------------------------------------------------------------

_aktiv: Logbuch | None = None


def verbinde(logbuch: Logbuch | None) -> None:
    """Macht dieses Logbuch zum aktiven: Ab jetzt schreiben alle `vermerke`-Aufrufe dorthin."""
    global _aktiv
    _aktiv = logbuch


def aktiv() -> Logbuch | None:
    return _aktiv


def vermerke(art: str, **daten: Any) -> bool:
    """Hängt einen Eintrag ans aktive Logbuch. **Wirft nie**; ohne aktives Logbuch geschieht nichts."""
    try:
        logbuch = _aktiv
        return logbuch.vermerke(art, **daten) if logbuch is not None else False
    except Exception:  # noqa: BLE001
        logger.exception('Logbuch: Eintrag %r gescheitert', art)
        return False


def seit(zeitpunkt: datetime, bis: datetime | None = None) -> Zusammenfassung:
    """Was seit `zeitpunkt` geschah (aktives Logbuch); ohne eines eine leere Zusammenfassung."""
    if _aktiv is None:
        zeitpunkt = zeitpunkt if zeitpunkt.tzinfo else zeitpunkt.replace(tzinfo=timezone.utc)
        return Zusammenfassung(seit=zeitpunkt, bis=bis or datetime.now(zeitpunkt.tzinfo))
    return _aktiv.seit(zeitpunkt, bis)


def fehler_des_laufs(jobs: Iterable[Any]) -> None:
    """Hält fest, welche Schritte eines Laufs der Hintergrundarbeit scheiterten (nur der Name, nie der Fehlertext)."""
    for job in jobs:
        try:
            if not getattr(job, 'ok', True):
                vermerke('fehler', was=str(getattr(job, 'name', '') or ''))
        except Exception:  # noqa: BLE001
            logger.exception('Logbuch: Fehler eines Laufs nicht vermerkt')


__all__ = ['ARTEN', 'Ereignis', 'Logbuch', 'Zusammenfassung', 'aktiv', 'drei_zeilen', 'fehler_des_laufs', 'fehler_satz', 'gruppen',
           'seit', 'seit_text', 'verbinde', 'vermerke', 'zusammenfassen']
