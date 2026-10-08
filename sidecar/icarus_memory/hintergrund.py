"""Die Steuerung der Hintergrundarbeit: ohne Nacht, nach Nutzen, mit Rücksicht.

Viele Menschen schalten den Rechner nachts aus. Die Hintergrundarbeit hängt
deshalb nicht an „nachts“, sondern läuft **immer, wenn die App läuft**, in
kleinen Häppchen und mit Pausen, und tritt zurück, sobald ein Mensch am Rechner
arbeitet. Die Regel und die Bestandsaufnahme stehen in `docs/46-hintergrund.md`.

Dieses Modul kopiert keine Arbeit. Die Schritte selbst (Mailaufnahme,
Einordnung, Lagen, voller Durchgang) bleiben, wo sie sind (`scheduler.py`,
`server._wire_scheduler`). Hier steht nur, **wann** und **in welcher
Reihenfolge** sie laufen dürfen:

* `Steuerung.sperre()`: ob der Hintergrund gerade zurücktritt (vom Menschen
  pausiert, jemand arbeitet, eine Antwort entsteht) und warum.
* `Steuerung.naechste_quellen()`: welche Quellen als Nächstes eingeordnet werden,
  nach Nutzen: erst, was morgen zählt, dann Neues, dann der Rückstand von neu nach alt.
* `Steuerung.pause_nach()`: wie lange nach einem Häppchen geruht wird.
* `ModellAmpel`: höchstens ein Modellaufruf zugleich, die Antwort hat Vorrang.
* `Steuerung.stand()`: Fortschritt, gemessene Rate und die Schätzung, wann es fertig ist.

Der Zustand, der einen Neustart überdauern muss (Pause des Menschen, letzter
voller Durchgang, Messpunkte der Rate), steht in `hintergrund.json` im
Datenordner. Die Schlange selbst braucht keinen eigenen Speicher: Was noch
offen ist, steht im Bestand (`working_memory_sources`), und dort geht es nach
einem Neustart weiter, wo es stand.

Nie verhindert der Hintergrund den Schlaf des Rechners (kein `caffeinate`,
keine Energiesperre). Er arbeitet, solange der Rechner ohnehin wach ist.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

#: Ruhe nach der letzten Eingabe des Menschen, bevor der Hintergrund wieder arbeitet.
RUHE_NACH_EINGABE_S = 20.0
#: Umgebungsvariable, die die Ruhe überschreibt (Sekunden). Nur für Prüfungen, die etwas anderes prüfen
#: als die Rücksicht, und deshalb nicht 20 s nach jeder Anfrage warten sollen.
RUHE_ENV = 'KINGFISHER_HINTERGRUND_RUHE_S'
#: Anteil der Zeit, in der der Hintergrund höchstens arbeitet; der Rest ist Pause.
ARBEITSANTEIL = 0.5
#: Kürzeste und längste Pause zwischen zwei Häppchen.
PAUSE_MIN_S = 2.0
PAUSE_MAX_S = 30.0
#: Wie lange nach dem Start der erste volle Durchgang frühestens läuft, wenn noch keiner gemerkt ist.
#: Wer den Rechner morgens einschaltet, soll nicht als Erstes den teuersten Durchgang bekommen.
ANLAUF_S = 5 * 60
#: Termine so weit voraus zählen als „morgen“.
TAGE_VORAUS = 3
#: So jung gilt eine Quelle als „neu“.
NEU_TAGE = 14
#: Wie viele jüngere Quellen nach offenen Fristen durchsucht werden (Regeln, kein Modell).
FRISTEN_KANDIDATEN = 300
#: Wie viele Quellen je Person eines anstehenden Termins vorgezogen werden.
JE_TEILNEHMER = 30
#: Wie lange die geordnete Schlange gilt, bevor sie neu aus dem Bestand gebildet wird.
PLAN_GILT_S = 60.0
#: Eine ausgegebene, aber nicht erledigte Quelle wird so lange nicht erneut vorgezogen
#: (der ordentliche Durchlauf findet sie trotzdem).
ZURUECKGESTELLT_S = 3600.0
#: Messpunkte der Rate: Abstand, höchstens so viele, und was als ununterbrochener Lauf gilt.
PROBE_ABSTAND_S = 60.0
PROBEN_MAX = 360
LUECKE_S = 3 * PROBE_ABSTAND_S
#: Mindestens so viel gemessene Laufzeit, bevor eine Schätzung genannt wird.
MESSZEIT_MIN_S = 5 * 60.0

STUFEN = ('morgen', 'neu', 'rueckstand')
STUFEN_TEXT = {
    'morgen': 'Was morgen zählt: Termine der nächsten Tage, ihre Beteiligten, Post von heute und gestern, offene Fristen',
    'neu': 'Neues der letzten zwei Wochen',
    'rueckstand': 'Der Rückstand, von neu nach alt',
}
GRUND_TEXT = {
    'akku': 'Die automatische Hintergrundverarbeitung pausiert im Akkubetrieb. Am Netzteil geht es weiter; Lesen und direkte Anfragen bleiben möglich.',
    'energie_unbekannt': 'Der aktuelle Energiestatus des Macs fehlt. Die automatische Hintergrundverarbeitung wartet auf die Meldung der App.',
    'pausiert': 'Pausiert. Kingfisher lernt weiter, wenn du „Weiter“ wählst.',
    'antwort': 'Kingfisher lernt weiter, sobald die Antwort fertig ist; du musst nichts tun.',
    # Fremdprobe 3, Befund 8: „Wartet, solange du arbeitest.“ las sich, als solle man aufhören zu arbeiten.
    'nutzer': 'Kingfisher lernt weiter, sobald du eine Pause machst; du musst nichts tun.',
}
SATZ_ANBLEIBEN = 'Es geht schneller, wenn der Rechner heute anbleibt.'


# -- Wer gerade arbeitet ------------------------------------------------------

_ORT = threading.local()


class BackgroundInterrupted(BaseException):
    """Intentional pause, not a provider failure or a source retry/backoff.

    Unwinds the active job to the scheduler tick so its locks and restore lease
    are released. Ordinary Exception handlers must not mark sources as failed.
    """


@contextmanager
def als_hintergrund(sperre: Callable[[], str | None] | None = None, *,
                    stopped: Callable[[], bool] | None = None) -> Iterator[None]:
    """Kennzeichnet den laufenden Faden als Hintergrund, samt der Sperre seiner Steuerung.

    Die Sperre hängt am Faden, nicht am Modul: Zwei Apps in einem Prozess (Tests)
    bremsen sich so nicht gegenseitig.
    """
    vorher = getattr(_ORT, 'sperre', None), getattr(_ORT, 'hinten', False), getattr(_ORT, 'stopped', None)
    _ORT.hinten, _ORT.sperre, _ORT.stopped = True, sperre, stopped
    try:
        yield
    finally:
        _ORT.sperre, _ORT.hinten, _ORT.stopped = vorher


def im_hintergrund() -> bool:
    return bool(getattr(_ORT, 'hinten', False))


def niedrige_prioritaet(schritte: int = 10) -> bool:
    """Senkt die Priorität des laufenden Fadens (Linux, also auch im Container).

    Auf Linux ist jeder Faden ein eigener Task; `setpriority` mit seiner Kennung
    bremst nur ihn, nicht die API. Auf anderen Systemen gälte `os.nice` für den
    ganzen Prozess, also auch für die Antworten; dort bleibt es bei den Pausen.
    Das Modell selbst läuft in einem eigenen Prozess (Ollama); es bremst die
    Ampel, nicht die Priorität.
    """
    if not sys.platform.startswith('linux') or not hasattr(os, 'setpriority'):
        return False
    try:
        kennung = threading.get_native_id()
        jetzt = os.getpriority(os.PRIO_PROCESS, kennung)
        os.setpriority(os.PRIO_PROCESS, kennung, min(19, jetzt + schritte))
        return True
    except OSError:
        return False


class ModellAmpel:
    """Höchstens ein lokaler Modellaufruf zugleich; die Antwort hat Vorrang.

    Ein Rechner hat einen Speicher, deshalb gibt es eine Ampel je Prozess
    (`AMPEL`). Die Antwort wartet höchstens auf den einen Aufruf des
    Hintergrunds, der schon läuft; der Hintergrund beginnt keinen neuen, solange
    eine Antwort läuft oder wartet oder seine Steuerung ihn sperrt. `parallel`
    sagt, ob beide Modelle zugleich in den Speicher passen (dann keine Wartezeit).
    """

    def __init__(self) -> None:
        self._bedingung = threading.Condition()
        self._vorne = 0
        self._hinten = 0
        self.parallel: Callable[[], bool] = lambda: False

    def _darf_parallel(self) -> bool:
        try:
            return bool(self.parallel())
        except Exception:  # noqa: BLE001 - im Zweifel nacheinander
            return False

    @contextmanager
    def vordergrund(self) -> Iterator[None]:
        with self._bedingung:
            self._vorne += 1
            while self._hinten and not self._darf_parallel():
                self._bedingung.wait(0.25)
        try:
            yield
        finally:
            with self._bedingung:
                self._vorne -= 1
                self._bedingung.notify_all()

    @contextmanager
    def hintergrund(self) -> Iterator[None]:
        sperre = getattr(_ORT, 'sperre', None)
        stopped = getattr(_ORT, 'stopped', None)
        with self._bedingung:
            while True:
                if stopped is not None and stopped():
                    raise BackgroundInterrupted('stopped')
                # Check energy even while another request occupies the model.
                gesperrt = sperre is not None and _gesperrt(sperre)
                if not (self._hinten or (self._vorne and not self._darf_parallel()) or gesperrt):
                    break
                self._bedingung.wait(0.25)
            self._hinten += 1
        try:
            yield
        finally:
            with self._bedingung:
                self._hinten -= 1
                self._bedingung.notify_all()

    def aufruf(self):
        """Der passende Weg für den laufenden Faden."""
        return self.hintergrund() if im_hintergrund() else self.vordergrund()

    def belegt(self) -> dict[str, int]:
        with self._bedingung:
            return {'vorne': self._vorne, 'hinten': self._hinten}


def _gesperrt(sperre: Callable[[], str | None]) -> bool:
    try:
        grund = sperre()
        if grund in ('akku', 'energie_unbekannt'):
            raise BackgroundInterrupted(grund)
        return grund is not None
    except Exception:  # noqa: BLE001 - eine kaputte Sperre darf den Hintergrund nicht für immer anhalten
        return False


AMPEL = ModellAmpel()


def speicher_reicht(geraet_gb: float | None, modelle: list[str]) -> bool:
    """Passen alle genannten Modelle zugleich in den Speicher dieses Rechners?

    Nur mit bekannten Größen aus dem Katalog (`model_recommendation.KATALOG`) und
    einem bekannten Gerät; sonst nein, also ein Aufruf nach dem anderen. Dasselbe
    Modell zweimal zählt einmal (es wird nur einmal geladen), teilt sich aber die
    Rechenzeit; auch dann gilt deshalb: nacheinander.
    """
    from .model_recommendation import KATALOG, _NUTZBARER_ANTEIL, normalisiere
    namen = [normalisiere(m) for m in modelle if m]
    if geraet_gb is None or len(namen) < 2 or len(set(namen)) < 2:
        return False
    groesse: dict[str, float] = {}
    for eintrag in KATALOG:
        groesse[normalisiere(eintrag.name)] = max(groesse.get(normalisiere(eintrag.name), 0.0), eintrag.speicher_gb)
    if any(n not in groesse for n in namen):
        return False
    return sum(groesse[n] for n in set(namen)) <= geraet_gb * _NUTZBARER_ANTEIL


# -- Aktivität des Menschen ---------------------------------------------------

#: Anfragen, bei denen eine Antwort formuliert wird.
def ist_antwort(methode: str, pfad: str) -> bool:
    if methode != 'POST':
        return False
    if pfad == '/chat':
        return True
    teile = pfad.strip('/').split('/')
    return (len(teile) >= 5 and teile[:3] == ['api', 'v1', 'conversations']
            and teile[4] == 'messages' and (len(teile) == 5 or teile[-1] == 'retry'))


def zaehlt_als_eingabe(methode: str, pfad: str, kopf: dict[bytes, bytes]) -> bool:
    """Eine Anfrage, hinter der ein Mensch steht.

    Abfragen, die die Oberfläche von selbst stellt (GET im Takt), zählen nicht,
    sonst hielte die Anzeige „Kingfisher lernt gerade“ das Lernen an. Die Helfer
    auf dem Mac melden sich mit dem Kopf `X-Icarus-Token`; auch sie sind kein
    Mensch. Tippen und Klicken meldet die Oberfläche gedrosselt über
    `POST /api/v1/hintergrund/aktiv`.
    """
    if b'x-icarus-token' in kopf:
        return False
    return methode not in ('GET', 'HEAD', 'OPTIONS')


class Aktivitaet:
    """Letzte Eingabe und laufende Antworten, nur im Speicher."""

    def __init__(self, uhr: Callable[[], float] = time.monotonic) -> None:
        self._uhr = uhr
        self._letzte = float('-inf')
        self._antworten = 0
        self._sperre = threading.Lock()

    def eingabe(self) -> None:
        with self._sperre:
            self._letzte = self._uhr()

    @contextmanager
    def antwort(self) -> Iterator[None]:
        with self._sperre:
            self._antworten += 1
            self._letzte = self._uhr()
        try:
            yield
        finally:
            with self._sperre:
                self._antworten -= 1
                self._letzte = self._uhr()

    def antwort_laeuft(self) -> bool:
        with self._sperre:
            return self._antworten > 0

    def ruhe_noch(self, ruhe_s: float) -> float:
        """Sekunden, bis die Ruhe nach der letzten Eingabe vorbei ist (0: ruhig)."""
        with self._sperre:
            return max(0.0, self._letzte + ruhe_s - self._uhr())


class AktivitaetsMiddleware:
    """Vermerkt Eingaben und laufende Antworten; ändert keine Anfrage."""

    def __init__(self, app, aktivitaet: Callable[[], Aktivitaet | None]) -> None:
        self.app, self._aktivitaet = app, aktivitaet

    async def __call__(self, scope, receive, send):
        aktivitaet = self._aktivitaet() if scope.get('type') == 'http' else None
        if aktivitaet is None:
            return await self.app(scope, receive, send)
        methode, pfad = scope.get('method', ''), scope.get('path', '')
        kopf = dict(scope.get('headers') or [])
        if zaehlt_als_eingabe(methode, pfad, kopf):
            aktivitaet.eingabe()
        if ist_antwort(methode, pfad):
            with aktivitaet.antwort():
                return await self.app(scope, receive, send)
        return await self.app(scope, receive, send)


# -- Reihenfolge nach Nutzen --------------------------------------------------

def _zeit(wert: Any) -> datetime | None:
    from .datumstext import iso_versuchen_utc
    return iso_versuchen_utc(wert)


@dataclass(frozen=True)
class Eintrag:
    episode_id: str
    stufe: str
    zeit: datetime


def ordnen(episodes: Any, jetzt: datetime) -> list[Eintrag]:
    """Alle offenen Quellen der Einordnung in der Reihenfolge nach Nutzen.

    1. **morgen**: Termine von heute bis `TAGE_VORAUS` Tage voraus; Quellen der
       Personen dieser Termine (über die Bezüge der Akten); Post von heute und
       gestern; jüngere Quellen mit einer offenen Frist (Regeln, kein Modell).
    2. **neu**: alles der letzten `NEU_TAGE` Tage.
    3. **rueckstand**: der Rest.

    Innerhalb jeder Stufe von neu nach alt: Für das Briefing zählt Aktualität,
    und wer nach etwas von vor drei Jahren fragt, findet es über den Suchindex
    auch ohne Einordnung (`docs/46-hintergrund.md`).
    """
    from .episodes import sql_rohquelle
    from .working_memory_store import ANALYSIS_VERSION
    offen_sql = ("NOT EXISTS (SELECT 1 FROM working_memory_sources w WHERE w.episode_id=e.id AND "
                 "((w.status='complete' AND (w.analysis_version=? OR w.retry_after>?)) "
                 "OR w.status IN ('deferred','dismissed') "
                 "OR (w.status='failed' AND w.retry_after>?)))")
    with episodes._lock:
        zeilen = episodes._conn.execute(
            f"SELECT e.id, e.kind, COALESCE(e.occurred_at, e.recorded_at) FROM episodes e "
            f"WHERE {sql_rohquelle('e')} AND {offen_sql}",
            (ANALYSIS_VERSION, time.time(), time.time())).fetchall()
    heute = jetzt.astimezone().date()
    tagesbeginn = datetime.combine(heute, datetime.min.time()).astimezone()
    gestern = tagesbeginn - timedelta(days=1)
    voraus = tagesbeginn + timedelta(days=TAGE_VORAUS + 1)
    neu_ab = tagesbeginn - timedelta(days=NEU_TAGE)
    alt = datetime(1970, 1, 1, tzinfo=timezone.utc)

    offen: dict[str, tuple[str, datetime]] = {}
    for kennung, art, roh in zeilen:
        offen[kennung] = (art, _zeit(roh) or alt)
    morgen: set[str] = set()
    for kennung, (art, zeit) in offen.items():
        if art == 'event' and tagesbeginn <= zeit < voraus:
            morgen.add(kennung)
        elif art == 'message' and gestern <= zeit <= jetzt + timedelta(hours=1):
            morgen.add(kennung)
    morgen |= _teilnehmer_quellen(episodes, tagesbeginn, voraus, offen)
    morgen |= _mit_offener_frist(episodes, heute, neu_ab, offen, morgen)

    def stufe(kennung: str, zeit: datetime) -> str:
        if kennung in morgen:
            return 'morgen'
        return 'neu' if zeit >= neu_ab else 'rueckstand'

    eintraege = [Eintrag(k, stufe(k, z), z) for k, (_, z) in offen.items()]
    rang = {s: i for i, s in enumerate(STUFEN)}
    # Termine innerhalb von „morgen“: der nächste zuerst; alles andere neu nach alt.
    return sorted(eintraege, key=lambda e: (rang[e.stufe], -e.zeit.timestamp(), e.episode_id))


def _teilnehmer_quellen(episodes: Any, von: datetime, bis: datetime,
                        offen: dict[str, tuple[str, datetime]]) -> set[str]:
    """Offene Quellen der Personen, die an Terminen im Fenster teilnehmen (Bezüge der Akten).

    Ohne berechnete Bezüge bleibt die Menge leer; die Termine selbst sind trotzdem vorn.
    """
    try:
        with episodes._lock:
            termine = [(k, z) for k, z in episodes._conn.execute(
                "SELECT id, COALESCE(occurred_at, recorded_at) FROM episodes WHERE kind='event'").fetchall()]
            im_fenster = [k for k, z in termine if (t := _zeit(z)) is not None and von <= t < bis]
            if not im_fenster:
                return set()
            platz = ','.join('?' * len(im_fenster))
            personen = [r[0] for r in episodes._conn.execute(
                f"SELECT DISTINCT sache FROM sach_bezuege WHERE art='person' AND episode_id IN ({platz})",
                im_fenster).fetchall()]
            gefunden: set[str] = set()
            for sache in personen[:50]:
                quellen = [r[0] for r in episodes._conn.execute(
                    "SELECT DISTINCT episode_id FROM sach_bezuege WHERE sache=?", (sache,)).fetchall()]
                quellen = [q for q in quellen if q in offen]
                quellen.sort(key=lambda q: offen[q][1], reverse=True)
                gefunden.update(quellen[:JE_TEILNEHMER])
            return gefunden
    except Exception:  # noqa: BLE001 - ohne Bezüge (etwa alter Bestand) geht es ohne diese Stufe weiter
        return set()


def _mit_offener_frist(episodes: Any, heute: date, neu_ab: datetime,
                       offen: dict[str, tuple[str, datetime]], schon: set[str]) -> set[str]:
    from .fristen import fristen_in
    kandidaten = sorted((k for k, (_, z) in offen.items() if z >= neu_ab - timedelta(days=46) and k not in schon),
                        key=lambda k: offen[k][1], reverse=True)[:FRISTEN_KANDIDATEN]
    gefunden: set[str] = set()
    for kennung in kandidaten:
        with episodes._lock:
            zeile = episodes._conn.execute("SELECT body FROM episodes WHERE id=?", (kennung,)).fetchone()
        if zeile is None:
            continue
        try:
            if any(f.datum >= heute for f in fristen_in(zeile[0] or '', offen[kennung][1]).fristen):
                gefunden.add(kennung)
        except Exception:  # noqa: BLE001 - eine unlesbare Quelle ist keine Frist
            continue
    return gefunden


def zaehlen(episodes: Any) -> dict[str, int]:
    """Fortschritt der Einordnung: erledigt (auch zurückgestellt oder ausgeschlossen) und gesamt."""
    from .episodes import sql_rohquelle
    from .working_memory_store import ANALYSIS_VERSION
    with episodes._lock:
        gesamt, fertig = episodes._conn.execute(
            f"SELECT COUNT(*), SUM(CASE WHEN (w.status='complete' AND w.analysis_version=?) "
            f"OR w.status IN ('deferred','dismissed') THEN 1 ELSE 0 END) "
            f"FROM episodes e LEFT JOIN working_memory_sources w ON w.episode_id=e.id WHERE {sql_rohquelle('e')}",
            (ANALYSIS_VERSION,)).fetchone()
    return {'gesamt': int(gesamt or 0), 'fertig': int(fertig or 0)}


# -- Schätzung ----------------------------------------------------------------

def rate(proben: list[list[float]]) -> float | None:
    """Quellen je Sekunde Laufzeit, aus aufeinanderfolgenden Messpunkten ohne Lücke.

    Die Nacht, in der der Rechner aus war, ist eine Lücke und zählt nicht: Die
    Rate gilt für die Zeit, in der Kingfisher läuft.
    """
    zeit = menge = 0.0
    for (t0, f0), (t1, f1) in zip(proben, proben[1:]):
        abstand = t1 - t0
        if 0 < abstand <= LUECKE_S:
            zeit += abstand
            menge += max(0.0, f1 - f0)
    if zeit < MESSZEIT_MIN_S or menge <= 0:
        return None
    return menge / zeit


_TAGE = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')


def _tageszeit(stunde: int) -> str:
    if 5 <= stunde < 10:
        return 'Morgen'
    if 10 <= stunde < 12:
        return 'Vormittag'
    if 12 <= stunde < 14:
        return 'Mittag'
    if 14 <= stunde < 18:
        return 'Nachmittag'
    if 18 <= stunde < 22:
        return 'Abend'
    return 'Nacht'


def wann_text(ziel: datetime, jetzt: datetime) -> str:
    """„in etwa einer Stunde“, „heute Abend“, „morgen Mittag“, „am Freitag“, „in etwa drei Wochen“."""
    ziel, jetzt = ziel.astimezone(), jetzt.astimezone()
    rest = (ziel - jetzt).total_seconds()
    if rest < 45 * 60:
        return 'in weniger als einer Stunde'
    if rest < 90 * 60:
        return 'in etwa einer Stunde'
    tage = (ziel.date() - jetzt.date()).days
    zeit = _tageszeit(ziel.hour)
    if tage in (0, 1):
        tag = 'heute' if tage == 0 else 'morgen'
        return f'{tag} früh' if zeit == 'Morgen' else f'{tag} {zeit}'
    if tage < 7:
        return f'am {_TAGE[ziel.weekday()]}'
    wochen = round(tage / 7)
    zahl = {1: 'einer', 2: 'zwei', 3: 'drei', 4: 'vier'}.get(wochen)
    if zahl is None:
        return 'in mehr als einem Monat'
    return f'in etwa {zahl} Woche' + ('' if wochen == 1 else 'n')


# -- Die Steuerung ------------------------------------------------------------

class Steuerung:
    """Wann und in welcher Reihenfolge der Hintergrund arbeitet; der Zustand überdauert Neustarts."""

    def __init__(self, datei: Path | None, episodes: Callable[[], Any], *,
                 uhr: Callable[[], float] = time.monotonic,
                 wanduhr: Callable[[], datetime] = lambda: datetime.now().astimezone(),
                 ruhe_s: float = RUHE_NACH_EINGABE_S,
                 external_gate: Callable[[], str | None] = lambda: None) -> None:
        self.external_gate = external_gate
        self._datei = datei
        self._episodes = episodes
        self._uhr = uhr
        self._wanduhr = wanduhr
        self.ruhe_s = ruhe_s
        self.aktivitaet = Aktivitaet(uhr)
        self._sperre = threading.Lock()
        self._plan: list[Eintrag] = []
        self._plan_von: tuple[Any, float] | None = None
        self._ausgegeben: dict[str, float] = {}
        self._letzte_probe = float('-inf')
        self._zustand = self._laden()

    # -- Zustand auf der Platte -------------------------------------------

    def _laden(self) -> dict[str, Any]:
        roh: Any = {}
        if self._datei is not None:
            try:
                roh = json.loads(self._datei.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                roh = {}
        roh = roh if isinstance(roh, dict) else {}
        proben = [p for p in roh.get('proben') or [] if isinstance(p, list) and len(p) == 2
                  and all(isinstance(x, (int, float)) for x in p)]
        voller = roh.get('voller_lauf')
        return {'pausiert': roh.get('pausiert') is True,
                'voller_lauf': voller if isinstance(voller, str) and _zeit(voller) else None,
                'proben': proben[-PROBEN_MAX:]}

    def _speichern(self) -> None:
        if self._datei is None:
            return
        from .atomic import write_text_atomic
        try:
            write_text_atomic(self._datei, json.dumps(self._zustand, ensure_ascii=False))
        except OSError:
            pass  # Die Anzeige verliert höchstens Messpunkte; die Arbeit selbst steht im Bestand.

    # -- Pause und Rücksicht ----------------------------------------------

    @property
    def pausiert(self) -> bool:
        return self._zustand['pausiert']

    def pausieren(self, ja: bool) -> None:
        with self._sperre:
            self._zustand['pausiert'] = bool(ja)
            self._speichern()

    def sperre(self) -> str | None:
        """Warum der Hintergrund gerade zurücktritt, oder `None`, wenn er arbeiten darf."""
        if self._zustand['pausiert']:
            return 'pausiert'
        external = self.external_gate()
        if external is not None:
            return external
        if self.aktivitaet.antwort_laeuft():
            return 'antwort'
        if self.aktivitaet.ruhe_noch(self.ruhe_s) > 0:
            return 'nutzer'
        return None

    def wartezeit(self) -> float:
        """Wie lange der Takt nach einer Sperre wartet, bevor er erneut nachsieht."""
        if self._zustand['pausiert'] or self.external_gate() is not None:
            return PAUSE_MAX_S
        return min(PAUSE_MAX_S, max(PAUSE_MIN_S, self.aktivitaet.ruhe_noch(self.ruhe_s)))

    @staticmethod
    def pause_nach(dauer_s: float) -> float:
        """Drosselung: nach einem Häppchen so lange ruhen, dass höchstens `ARBEITSANTEIL` der Zeit gearbeitet wird."""
        return min(PAUSE_MAX_S, max(PAUSE_MIN_S, dauer_s * (1 - ARBEITSANTEIL) / ARBEITSANTEIL))

    # -- Voller Durchgang --------------------------------------------------

    def erster_voller_lauf(self, intervall: timedelta) -> datetime:
        """Wann `_last_at` des Zeitplans nach einem Neustart steht: gemerkt, sonst so, dass er nach dem Anlauf fällig wird."""
        gemerkt = _zeit(self._zustand['voller_lauf'])
        if gemerkt is not None:
            return gemerkt
        return self._wanduhr() - intervall + timedelta(seconds=ANLAUF_S)

    def voller_lauf_fertig(self, wann: datetime) -> None:
        with self._sperre:
            self._zustand['voller_lauf'] = wann.astimezone().isoformat()
            self._speichern()

    # -- Reihenfolge ------------------------------------------------------

    def _geplant(self) -> list[Eintrag]:
        episodes = self._episodes()
        jetzt = self._uhr()
        if (self._plan_von is None or self._plan_von[0] is not episodes
                or jetzt - self._plan_von[1] >= PLAN_GILT_S or not self._plan):
            try:
                self._plan = ordnen(episodes, self._wanduhr())
            except Exception:  # noqa: BLE001 - ohne Plan läuft der ordentliche Durchlauf
                self._plan = []
            self._plan_von = (episodes, jetzt)
        return self._plan

    def naechste_quellen(self, limit: int = 5, *, nur: str | None = None) -> list[str]:
        """Die nächsten offenen Quellen nach Nutzen; bereits ausgegebene ruhen eine Weile."""
        with self._sperre:
            jetzt = self._uhr()
            self._ausgegeben = {k: t for k, t in self._ausgegeben.items() if jetzt - t < ZURUECKGESTELLT_S}
            auswahl = [e.episode_id for e in self._geplant()
                       if e.episode_id not in self._ausgegeben and (nur is None or e.stufe == nur)][:limit]
            for kennung in auswahl:
                self._ausgegeben[kennung] = jetzt
            return auswahl

    def dringend_offen(self) -> bool:
        """Ob noch etwas aus der Stufe „morgen“ wartet (dann vor neuen Uploads)."""
        with self._sperre:
            return any(e.stufe == 'morgen' and e.episode_id not in self._ausgegeben for e in self._geplant())

    def schlange(self) -> list[dict[str, Any]]:
        with self._sperre:
            plan = self._geplant()
        return [{'stufe': s, 'text': STUFEN_TEXT[s], 'offen': sum(1 for e in plan if e.stufe == s)} for s in STUFEN]

    # -- Messen und schätzen ----------------------------------------------

    def probe(self) -> None:
        """Ein Messpunkt (Wanduhr, erledigte Quellen), höchstens alle `PROBE_ABSTAND_S` Sekunden."""
        jetzt = self._uhr()
        if jetzt - self._letzte_probe < PROBE_ABSTAND_S:
            return
        self._letzte_probe = jetzt
        try:
            fertig = zaehlen(self._episodes())['fertig']
        except Exception:  # noqa: BLE001
            return
        with self._sperre:
            proben = self._zustand['proben']
            proben.append([self._wanduhr().timestamp(), float(fertig)])
            del proben[:-PROBEN_MAX]
            self._speichern()

    def stand(self, *, freigegeben: bool, mit_modell: bool) -> dict[str, Any]:
        """Alles für `GET /api/v1/hintergrund` und die Anzeige „Kingfisher lernt gerade“."""
        try:
            zahlen = zaehlen(self._episodes())
        except Exception:  # noqa: BLE001
            zahlen = {'gesamt': 0, 'fertig': 0}
        offen = max(0, zahlen['gesamt'] - zahlen['fertig'])
        je_s = rate(self._zustand['proben'])
        grund = self.sperre()
        if not freigegeben:
            zustand = 'aus'
        elif not mit_modell:
            zustand = 'ohne_modell'
        elif offen == 0:
            zustand = 'fertig'
        elif grund == 'pausiert':
            zustand = 'pausiert'
        elif grund is not None:
            zustand = 'wartet'
        else:
            zustand = 'laeuft'
        schaetzung = None
        if zustand in ('laeuft', 'wartet') and je_s and grund not in ('akku', 'energie_unbekannt'):
            sekunden = offen / je_s
            jetzt = self._wanduhr()
            ziel = jetzt + timedelta(seconds=sekunden)
            schaetzung = {'sekunden': int(round(sekunden)), 'fertig_um': ziel.isoformat(), 'text': wann_text(ziel, jetzt)}
        satz = None
        if schaetzung is not None and schaetzung['sekunden'] > 2 * 3600:
            satz = SATZ_ANBLEIBEN
        return {
            'zustand': zustand,
            'grund': GRUND_TEXT.get(grund or '') if (zustand in ('pausiert', 'wartet')
                      or freigegeben and grund in ('akku', 'energie_unbekannt')) else None,
            'pausiert': self.pausiert,
            'fortschritt': {**zahlen, 'offen': offen},
            'rate_pro_stunde': None if not je_s else round(je_s * 3600, 1),
            'schaetzung': schaetzung,
            'schaetzung_text': schaetzung['text'] if schaetzung else ('noch unklar' if zustand in ('laeuft', 'wartet') else None),
            'satz': satz,
            'schlange': self.schlange() if zustand not in ('aus', 'fertig') else [],
        }


# -- Einbau -------------------------------------------------------------------

def einbauen(app: Any, guard: list[Any], data_dir: Callable[[], Path]) -> Steuerung:
    """Der eine Einbau in `server.create_app`: Steuerung, Aktivität, Ampel, Routen, Anschluss an den Zeitplan."""
    from fastapi.responses import Response

    try:
        ruhe_s = max(0.0, float(os.environ.get(RUHE_ENV, RUHE_NACH_EINGABE_S)))
    except ValueError:
        ruhe_s = RUHE_NACH_EINGABE_S
    from .host_power import install_routes as install_power_routes
    power = install_power_routes(app, guard, data_dir)
    steuerung = Steuerung(data_dir() / 'hintergrund.json', lambda: app.state.episodes, ruhe_s=ruhe_s, external_gate=power.reason)
    app.state.hintergrund = steuerung
    app.add_middleware(AktivitaetsMiddleware, aktivitaet=lambda: getattr(getattr(app.state, 'hintergrund', None), 'aktivitaet', None))

    def modelle_passen() -> bool:
        from .device_profile import load_device_profile
        from .model_recommendation import geraet_aus_profil
        from .model_roles import lese_wahlen
        wahlen = lese_wahlen(getattr(app.state.settings, 'model_roles', None))
        standard = getattr(app.state.settings, 'model', '') or ''
        namen = [(wahlen[r].modell if r in wahlen and wahlen[r].modell else standard) for r in ('antwort', 'hintergrund')]
        return speicher_reicht(geraet_aus_profil(load_device_profile(data_dir())).modellspeicher_gb, namen)

    AMPEL.parallel = modelle_passen

    # Der Zeitplan entsteht beim Bau des Agenten (`_wire_scheduler`), also vor diesem Einbau. Fehlt er (ein
    # von außen übergebener Agent in Prüfungen), bleibt es beim alten Verhalten; die Routen gehen trotzdem.
    scheduler = getattr(app.state, 'scheduler', None)
    if scheduler is not None:
        scheduler.anschliessen(steuerung)

    def stand() -> dict[str, Any]:
        plan = app.state.settings.schedule
        provider = None
        try:
            from .model_roles import rollen_von
            provider = rollen_von(app).provider('hintergrund')
        except Exception:  # noqa: BLE001
            provider = None
        mit_modell = bool(plan.with_model and getattr(provider, 'is_local', False))
        return steuerung.stand(freigegeben=bool(plan.enabled), mit_modell=mit_modell)

    @app.get('/api/v1/hintergrund', dependencies=guard)
    def hintergrund() -> dict[str, Any]:
        return stand()

    @app.post('/api/v1/hintergrund/pause', dependencies=guard)
    def hintergrund_pause() -> dict[str, Any]:
        steuerung.pausieren(True)
        return stand()

    @app.post('/api/v1/hintergrund/weiter', dependencies=guard)
    def hintergrund_weiter() -> dict[str, Any]:
        steuerung.pausieren(False)
        wecken = getattr(getattr(app.state, 'scheduler', None), 'wecken', None)
        if callable(wecken):
            wecken()
        return stand()

    @app.post('/api/v1/hintergrund/aktiv', dependencies=guard, status_code=204, response_class=Response)
    def hintergrund_aktiv() -> None:
        # Die Middleware hat die Eingabe schon vermerkt; die Route bestätigt nur.
        return None

    from .autostart import register as register_autostart
    register_autostart(app, guard, data_dir)
    return steuerung


__all__ = [
    'AMPEL', 'Aktivitaet', 'AktivitaetsMiddleware', 'BackgroundInterrupted', 'ModellAmpel', 'Steuerung', 'als_hintergrund', 'einbauen',
    'im_hintergrund', 'ist_antwort', 'niedrige_prioritaet', 'ordnen', 'rate', 'speicher_reicht', 'wann_text',
    'zaehlen', 'zaehlt_als_eingabe',
]
