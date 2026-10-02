"""Termine im Gedächtnis: jeder Termin einer freigegebenen Kalenderquelle als Rohquelle.

Bisher las das Produkt Termine bei jeder Frage live aus dem Kalender (±30 Tage,
der Mac-Adapter nur das laufende Jahr). Ein vergangenes Treffen war damit für
Rückblicke unsichtbar, eine Terminnotiz ging verloren, und die Suche fand
keinen Termin. Hier wird jeder Termin zur **Episode** der Art `event`: mit
Titel, Beginn und Ende, Ort, Teilnehmern (Name und Adresse) und Notiz. Sie ist
damit suchbar (Einordnung wie bei jeder Quelle, `working_memory_*`) und als
Beleg zitierbar.

## Was gilt

* **Rohmaterial, keine Fakten.** Ein Termin behauptet nichts über die Welt. Was
  daraus als Wissen folgen könnte, entsteht nur über Vorschlag und Annahme
  (`docs/10-verdichtung.md`). Deshalb bleibt die Verdichtung außen vor
  (`EpisodeStore.pending` überspringt Termine).
* **Kein zweites Versionssystem.** Ein Termin ist eine Quelle mit Schlüssel
  (`source_key`). Ein verschobener oder geänderter Termin ist eine neue Fassung
  derselben Quelle (`source_versions.track_source`: Wissen aus der alten sperren,
  alte Fassung ausschließen, Zeiger umstellen), keine Dublette. Ein gelöschter
  oder abgesagter Termin ist eine entzogene Quelle (`ignore`, mit Marke
  `entzogen:kalender`), die Episode bleibt als Nachweis erhalten.
* **Inkrementell.** Der Fingerabdruck einer Fassung ist der Digest ihres Textes,
  und der Text enthält alles Erhebliche (Titel, Zeit, Ort, Teilnehmer, Notiz).
  Ein Abgleich liest je Abschnitt nur Schlüssel und Digest der aktuellen
  Fassungen und fasst nur an, was abweicht.
* **Nur mit Freigabe.** Ohne freigegebene Quelle wird nichts geschrieben; wer
  eine Quelle trennt oder abwählt, entzieht ihre Termine (`entziehen_ohne_freigabe`).

## Zeitraum

Die Konstanten stehen an einer Stelle (unten). Der Mac-Arbeiter fragt sie über
den Adapterzustand ab (`memory_window`), Google, CalDAV und Abonnements liest
der Zeitplan (`kalender_job`). Die Live-Anzeige (Kalenderseite, Briefing ±30
Tage) bleibt davon unberührt.

## Grenzen

Ein Abgleich arbeitet in Abschnitten (`ABSCHNITT_TAGE`) mit höchstens
`MAX_TERMINE_JE_ABSCHNITT` Terminen. Nur ein **vollständig gelesener** Abschnitt
darf Termine entziehen: Was darin fehlt, gilt als gelöscht. Ein leerer
Abschnitt entzieht nichts, weil er ebenso von einem stillen Lesefehler stammen
kann. CalDAV und Abonnements liefern Wiederholungen nicht ausgeklappt (siehe
`connectors/calendar.py`): Serientermine erscheinen dort nur einmal.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Iterable, Sequence

from . import logbuch
from .connectors.calendar import Event
from .datumstext import MONATE
from .episodes import ENTZUG_MARKE, EpisodeError, EpisodeKind, EpisodeState, EpisodeStore, digest_of
from .model import Provenance, SourceType, ensure_aware, now, user_timezone
from .source_versions import invalidate_with_corrections, track_source

# -- Zeitraum: die einzige Stelle -------------------------------------------

VERGANGENHEIT_TAGE = 3 * 365
"""Wie weit zurück Termine ins Gedächtnis kommen."""

ZUKUNFT_TAGE = 365
"""Wie weit voraus."""

ABSCHNITT_TAGE = 90
"""Größe eines Abgleichabschnitts (Mac-Arbeiter und Zeitplan)."""

MAX_TERMINE_JE_ABSCHNITT = 20000
"""Obergrenze je Abschnitt; darüber lehnt der Adapter ab, statt still zu kürzen."""

MAC_QUELLE = "mac-calendar"
"""Kennung der Mac-Quelle. Ihre Kalender hängen als `mac-calendar/<Kurzhash>` daran."""

ENTZUG_GRUND = "kalender"
_SCHLUESSEL = "cal:"
_HERKUNFT = "calendar:"

_WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
_MONATE = MONATE


def fenster(at: datetime | None = None) -> tuple[datetime, datetime]:
    """Der Zeitraum, den das Gedächtnis von einer Kalenderquelle hält."""
    at = ensure_aware(at) or now()
    return at - timedelta(days=VERGANGENHEIT_TAGE), at + timedelta(days=ZUKUNFT_TAGE)


def abschnitte(von: datetime, bis: datetime) -> list[tuple[datetime, datetime]]:
    """Zerlegt `von`..`bis` in aneinanderstoßende Abschnitte von `ABSCHNITT_TAGE`."""
    ergebnis, start = [], von
    while start < bis:
        ende = min(start + timedelta(days=ABSCHNITT_TAGE), bis)
        ergebnis.append((start, ende))
        start = ende
    return ergebnis


def quelle_fuer_mac(kalender_id: str) -> str:
    """Quellenkennung eines Mac-Kalenders (die Kalender-ID selbst ist zu lang und frei geformt)."""
    return f"{MAC_QUELLE}/{hashlib.sha256(kalender_id.encode()).hexdigest()[:12]}"


def schluessel_praefix(quelle: str) -> str:
    """Präfix aller Quellenschlüssel einer Quelle; `MAC_QUELLE` allein meint alle Mac-Kalender."""
    return _SCHLUESSEL + quelle + (":" if quelle != MAC_QUELLE else "/")


def quelle_schluessel(quelle: str, uid: str) -> str:
    return f"{_SCHLUESSEL}{quelle}:{hashlib.sha256(uid.encode()).hexdigest()[:32]}"


def herkunft(quelle: str, uid: str) -> str:
    """`source_ref` der Episode: lesbar, mit der UID des Termins am Ende."""
    return f"{_HERKUNFT}{quelle}:{uid}"


def uid_aus_herkunft(source_ref: str | None) -> str | None:
    """Umkehrung von `herkunft`: die UID des Termins, sonst None."""
    if not source_ref or not source_ref.startswith(_HERKUNFT):
        return None
    _, _, rest = source_ref[len(_HERKUNFT):].partition(":")
    return rest or None


# -- Text und Fingerabdruck --------------------------------------------------


def _wann(termin: Event) -> str:
    zone = user_timezone()
    beginn, ende = termin.start, termin.end

    def tag(moment: datetime) -> str:
        return f"{_WOCHENTAGE[moment.weekday()]}, {moment.day}. {_MONATE[moment.month - 1]} {moment.year} ({moment:%d.%m.%Y})"

    if termin.all_day:
        # Ganztägige Termine tragen ein Datum ohne Uhrzeit; nicht in eine andere Zone umrechnen.
        text = "ganztägig, " + tag(beginn)
        if ende and ende.date() > (beginn + timedelta(days=1)).date():
            text += " bis " + tag(ende - timedelta(days=1))
        return text
    if zone is not None:
        beginn = beginn.astimezone(zone)
        ende = ende.astimezone(zone) if ende else None
    text = f"{tag(beginn)}, {beginn:%H:%M}"
    if ende is not None:
        text += f" bis {ende:%H:%M}" if ende.date() == beginn.date() else f" bis {tag(ende)}, {ende:%H:%M}"
    return text + " Uhr"


def termin_text(termin: Event, kalender: str = "") -> str:
    """Der Text der Rohquelle. Alles, was einen Termin ausmacht, steht darin."""
    zeilen = [f"Termin: {(termin.summary or '').strip() or '(ohne Titel)'}", f"Wann: {_wann(termin)}"]
    if termin.location and termin.location.strip():
        zeilen.append(f"Ort: {' '.join(termin.location.split())}")
    teilnehmer = _teilnehmer(termin)
    if teilnehmer:
        zeilen.append("Teilnehmer: " + ", ".join(teilnehmer))
    if kalender:
        zeilen.append(f"Kalender: {kalender}")
    if termin.notes and termin.notes.strip():
        zeilen += ["Notiz:", termin.notes.strip()]
    return "\n".join(zeilen)


def _teilnehmer(termin: Event) -> list[str]:
    return list(dict.fromkeys(a.strip() for a in termin.attendees if a and a.strip()))


def fingerabdruck(termin: Event, kalender: str = "") -> str:
    """Kennung einer Fassung: der Digest ihres Textes."""
    return digest_of(termin_text(termin, kalender))


# -- Abgleich ----------------------------------------------------------------


@dataclass
class Abgleich:
    """Was ein Abgleich getan hat. Jede Zahl ist ein Zähler, keine Schätzung."""

    neu: int = 0
    geaendert: int = 0
    unveraendert: int = 0
    wiederhergestellt: int = 0
    entzogen: int = 0
    ausserhalb: int = 0
    ausgeschlossen: int = 0
    """Vom Nutzer ausgeschlossene Termine, die unverändert blieben."""
    keine_freigabe: bool = False
    leer_ohne_entzug: bool = False
    fehler: list[str] = field(default_factory=list)

    def __iadd__(self, other: "Abgleich") -> "Abgleich":
        for name in ("neu", "geaendert", "unveraendert", "wiederhergestellt", "entzogen", "ausserhalb", "ausgeschlossen"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.keine_freigabe |= other.keine_freigabe
        self.leer_ohne_entzug |= other.leer_ohne_entzug
        self.fehler += other.fehler
        return self

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in (
            "neu", "geaendert", "unveraendert", "wiederhergestellt", "entzogen", "ausserhalb",
            "ausgeschlossen", "keine_freigabe", "leer_ohne_entzug", "fehler")}

    def summary(self) -> str:
        if self.keine_freigabe:
            return "Quelle nicht freigegeben; nichts aufgenommen."
        teile = [f"{self.neu} neu", f"{self.geaendert} geändert", f"{self.unveraendert} unverändert"]
        if self.wiederhergestellt:
            teile.append(f"{self.wiederhergestellt} wiederhergestellt")
        if self.entzogen:
            teile.append(f"{self.entzogen} entzogen")
        if self.ausgeschlossen:
            teile.append(f"{self.ausgeschlossen} vom Nutzer ausgeschlossen")
        if self.leer_ohne_entzug:
            teile.append("leerer Abschnitt, nichts entzogen")
        return ", ".join(teile)


class KalenderGedaechtnis:
    """Legt Termine als Episoden ab und hält sie mit dem Kalender im Gleichschritt.

    `lock` ist dieselbe Sperre wie bei Mail und Ordnern (Gesprächssperre): Aufnahme
    und Freigabeänderungen dürfen sich nicht überholen. Sie wird nur je Paket
    gehalten, nie um Netzabrufe; der Aufrufer darf sie beim Aufruf nicht halten.
    """

    PAKET = 100

    def __init__(self, episodes: EpisodeStore, claims, *, lock=None) -> None:
        self.episodes = episodes
        self.claims = claims
        self.lock = lock

    def _gesperrt(self):
        from contextlib import nullcontext
        return self.lock if self.lock is not None else nullcontext()

    def abgleichen(self, quelle: str, label: str, termine: Sequence[Event], von: datetime, bis: datetime,
                   *, erlaubt: Callable[[], bool] = lambda: True, at: datetime | None = None) -> Abgleich:
        """Gleicht den Abschnitt `von`..`bis` einer Quelle mit dem Gedächtnis ab.

        `termine` müssen alle Termine der Quelle in diesem Abschnitt sein (auch
        solche, die ihn nur berühren). Nur dann ist es zulässig, dass ein
        fehlender Termin als gelöscht gilt.
        """
        ergebnis = Abgleich()
        von, bis = ensure_aware(von), ensure_aware(bis)
        at = at or now()
        praefix = schluessel_praefix(quelle)
        bekannt = {kopf[0]: kopf for kopf in self.episodes.heads_with_prefix(praefix)}
        im_fenster = [t for t in termine if t.start is not None and t.end is not None
                      and ensure_aware(t.end) > von and ensure_aware(t.start) < bis]
        ergebnis.ausserhalb = len(termine) - len(im_fenster)
        gesehen: set[str] = set()
        schluessel_je_termin = _schluessel_je_termin(quelle, im_fenster)
        for start in range(0, len(im_fenster), self.PAKET):
            paket = im_fenster[start:start + self.PAKET]
            with self._gesperrt():
                if not erlaubt():
                    ergebnis.keine_freigabe = True
                    return ergebnis
                for termin, schluessel in zip(paket, schluessel_je_termin[start:start + self.PAKET]):
                    gesehen.add(schluessel)
                    try:
                        self._aufnehmen(termin, quelle, label, schluessel, herkunft(quelle, termin.uid),
                                        bekannt.get(schluessel), ergebnis, at)
                    except (EpisodeError, ValueError) as exc:
                        ergebnis.fehler.append(f"{type(exc).__name__}")
        # Ein leerer Abschnitt kann ebenso von einem Lesefehler stammen wie von einem
        # tatsächlich leeren Kalender; das eine ist harmlos, das andere löschte Jahre.
        fehlend = [k for k in bekannt.values() if k[0] not in gesehen and k[3] != EpisodeState.IGNORED.value
                   and k[4] and von <= ensure_aware(datetime.fromisoformat(k[4])) < bis]
        if fehlend and not im_fenster:
            ergebnis.leer_ohne_entzug = True
        elif fehlend:
            with self._gesperrt():
                if not erlaubt():
                    ergebnis.keine_freigabe = True
                    return ergebnis
                for kopf in fehlend:
                    self._entziehen(kopf[1])
                    ergebnis.entzogen += 1
        if ergebnis.neu:
            logbuch.vermerke('quellen', sorte='termin', anzahl=ergebnis.neu)
        return ergebnis

    def _aufnehmen(self, termin: Event, quelle: str, label: str, schluessel: str, ref: str,
                   kopf, ergebnis: Abgleich, at: datetime) -> None:
        text = termin_text(termin, label)
        digest = digest_of(text)
        if kopf is not None and kopf[2] == digest:
            if kopf[3] != EpisodeState.IGNORED.value:
                ergebnis.unveraendert += 1
            elif self._wiederherstellen(kopf[1]):
                ergebnis.wiederhergestellt += 1
            else:
                ergebnis.ausgeschlossen += 1
            return
        episode, neu = self.episodes.record(
            EpisodeKind.EVENT, (termin.summary or "").strip() or "(ohne Titel)", text,
            Provenance(source_type=SourceType.CALENDAR, source_ref=ref, captured_at=termin.start),
            occurred_at=termin.start, participants=_teilnehmer(termin), source_key=schluessel, at=at)
        geaendert = track_source(self.episodes, self.claims, schluessel, episode)
        if (episode.state is EpisodeState.IGNORED and episode.id != (kopf[1] if kopf else None)
                and self._wiederherstellen(episode.id, ersetzt=True)):
            # Ein Termin, der auf eine frühere Fassung zurückgesetzt wurde: Sie war nur ersetzt.
            ergebnis.wiederhergestellt += 1
        elif geaendert:
            ergebnis.geaendert += 1
        elif neu or kopf is None:
            ergebnis.neu += 1
        else:
            ergebnis.unveraendert += 1

    def _wiederherstellen(self, episode_id: str, *, ersetzt: bool = False) -> bool:
        """Öffnet eine vom Programm selbst ausgeschlossene Fassung wieder. Nutzerausschluss bleibt.

        Selbst ausgeschlossen heißt: mit Entzugsmarke (Kalender getrennt, Termin gelöscht) oder,
        mit `ersetzt`, eine frühere Fassung, die nur von einer neueren abgelöst wurde und nun
        wieder gilt (Termin zurückgesetzt).
        """
        episode = self.episodes.get(episode_id)
        if episode.state is not EpisodeState.IGNORED or not (
                ersetzt or any(t.startswith(ENTZUG_MARKE) for t in episode.tags)):
            return False
        try:
            self.episodes.reopen(episode_id)
        except EpisodeError:
            return False  # Berichtigung oder neuere Fassung: die Sperre bleibt bewusst stehen.
        return True

    def _entziehen(self, episode_id: str) -> None:
        # Erst Wissen sperren, dann ausschließen: bei Abbruch wiederholt der nächste Lauf.
        invalidate_with_corrections(self.episodes, self.claims, episode_id)
        self.episodes.ignore(episode_id, grund=ENTZUG_GRUND)

    def entziehen_ohne_freigabe(self, freigegeben: Callable[[str], bool]) -> int:
        """Entzieht die Termine aller Quellen, die `freigegeben(quelle)` verneint.

        Aufgerufen, wenn eine Kalenderquelle getrennt oder abgewählt wird, und bei
        jedem Zeitplanlauf (dann reicht ein bei einer Änderung übersehener Fall).
        """
        entzogen = 0
        with self._gesperrt():
            for schluessel, episode_id, _digest, zustand, _wann_ in self.episodes.heads_with_prefix(_SCHLUESSEL):
                quelle = schluessel[len(_SCHLUESSEL):].rpartition(":")[0]
                if zustand == EpisodeState.IGNORED.value or freigegeben(quelle):
                    continue
                self._entziehen(episode_id)
                entzogen += 1
        return entzogen

    def anzahl(self, quelle: str | None = None) -> int:
        """Aktuelle (nicht ausgeschlossene) Termine im Gedächtnis, je Quelle oder insgesamt."""
        praefix = schluessel_praefix(quelle) if quelle else _SCHLUESSEL
        return sum(1 for kopf in self.episodes.heads_with_prefix(praefix) if kopf[3] != EpisodeState.IGNORED.value)


def _schluessel_je_termin(quelle: str, termine: Sequence[Event]) -> list[str]:
    """Quellenschlüssel je Termin. Doppelte UIDs (Serie mit Ausnahme) bekommen den Beginn dazu."""
    zaehler: dict[str, int] = {}
    for termin in termine:
        zaehler[termin.uid] = zaehler.get(termin.uid, 0) + 1
    return [quelle_schluessel(quelle, termin.uid if zaehler[termin.uid] == 1
                              else f"{termin.uid}#{termin.start.isoformat()}") for termin in termine]


def kalender_job(gedaechtnis: KalenderGedaechtnis, quellen: Iterable, *, at: datetime | None = None,
                 erlaubt: Callable[[str], bool] = lambda quelle: True) -> dict[str, Abgleich]:
    """Liest jede Nicht-Mac-Quelle im Gedächtnisfenster und gleicht sie ab.

    `quellen`: Objekte mit `id`, `label` und `reader.events(days, at)`. Ein Lesefehler
    einer Quelle lässt ihre Termine unberührt (kein Löschbeweis) und die anderen
    Quellen weiterlaufen. Die Quelle liest abschnittsweise (`ABSCHNITT_TAGE`), damit
    Größenbegrenzungen der Anbieter (Google: Seitenzahl) nie still kürzen.
    """
    von, bis = fenster(at)
    ergebnisse: dict[str, Abgleich] = {}
    for quelle in quellen:
        summe = Abgleich()
        ergebnisse[quelle.id] = summe
        gesamt = getattr(quelle.reader, "ganzer_zeitraum", False)
        for a, b in ([(von, bis)] if gesamt else abschnitte(von, bis)):
            try:
                termine = quelle.reader.events(days=max(1, -(-int((b - a).total_seconds()) // 86400)), at=a)
            except Exception as exc:  # noqa: BLE001 - eine Quelle darf die anderen nicht anhalten
                summe.fehler.append(type(exc).__name__)
                continue
            if len(termine) > MAX_TERMINE_JE_ABSCHNITT:
                summe.fehler.append("zu viele Termine im Abschnitt")
                continue
            summe += gedaechtnis.abgleichen(quelle.id, quelle.label, termine, a, b,
                                            erlaubt=lambda q=quelle.id: erlaubt(q), at=at)
            if summe.keine_freigabe:
                break
    return ergebnisse
