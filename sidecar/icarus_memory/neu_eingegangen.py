"""Was auf Heute unter „Neu eingegangen“ steht: nur, was wirklich neu ist (V1, 25.10.2026).

Nach dem ersten Einlesen eines Postfachs ist alles „heute erfasst“, auch die Mail vom April 2025. Das ist Altbestand,
keine neue Post. Die Regel steht an dieser einen Stelle; Heute (`morning.compose`) und die Zusammenstellung der
Startseite (`server._dashboard_data`) fragen sie hier ab, die Oberfläche zeigt nur, was hier durchkommt.

Die Regel:

* Mit Quelldatum zählt das Quelldatum: neu ist, was am Bezugstag oder an einem der `FENSTER_TAGE` Tage davor
  entstand (Kalendertag in der Zeitzone des Briefings, wie `fristen.bezugstag`). Was später datiert ist als der
  Bezugstag (ein Termin in der Zukunft, eine Mail mit falsch gehender Uhr), ist nicht „eingegangen“.
* Ohne Quelldatum zählt die Erfassung, nach demselben Fenster – aber nicht, wenn die Quelle aus der
  Bestandsaufnahme eines Postfachs stammt (`mail_intake_items.lane = 'history'`, ohne Eintrag der Spur „live“): Dann
  sagt die Erfassung nur, wann Kingfisher den Bestand gelesen hat, nicht, wann etwas kam.

Quelldatum und Erfassung bleiben getrennte Angaben; hier wird keines aus dem anderen gemacht.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Iterable

FENSTER_TAGE = 2
"""Heute, gestern und vorgestern: Wer am Montag früh schaut, sieht die Post vom Samstag noch."""

MAX_KANDIDATEN = 100
"""Höchstens so viele neue Quellen werden für die Quellenberichte geprüft (`working_memory_context.reports`)."""


def _zone(jetzt: datetime) -> tzinfo:
    if jetzt.tzinfo is not None:
        return jetzt.tzinfo
    from .model import user_timezone
    return user_timezone() or timezone.utc


def _tag(zeitpunkt: datetime, zone: tzinfo) -> date:
    moment = zeitpunkt if zeitpunkt.tzinfo else zeitpunkt.replace(tzinfo=timezone.utc)
    return moment.astimezone(zone).date()


def _lesen(wert: datetime | str | None) -> datetime | None:
    if wert is None or isinstance(wert, datetime):
        return wert
    from .datumstext import iso_versuchen
    return iso_versuchen(wert)


def im_fenster(zeitpunkt: datetime | str | None, *, jetzt: datetime) -> bool:
    """Ob der Zeitpunkt auf den Bezugstag oder einen der `FENSTER_TAGE` Tage davor fällt."""
    moment = _lesen(zeitpunkt)
    if moment is None:
        return False
    zone = _zone(jetzt)
    abstand = (_tag(jetzt, zone) - _tag(moment, zone)).days
    return 0 <= abstand <= FENSTER_TAGE


def ist_neu(quelldatum: datetime | str | None, erfasst: datetime | str | None, *, jetzt: datetime,
            aus_bestand: bool = False) -> bool:
    """Die Regel für eine Quelle (siehe Modulkopf). Ein unlesbares Quelldatum zählt wie keines."""
    entstanden = _lesen(quelldatum)
    if entstanden is not None:
        return im_fenster(entstanden, jetzt=jetzt)
    return not aus_bestand and im_fenster(erfasst, jetzt=jetzt)


def fenster_beginn(jetzt: datetime) -> datetime:
    """Der früheste Zeitpunkt, der noch zählt: Mitternacht am ersten Tag des Fensters, in der Zone des Briefings."""
    zone = _zone(jetzt)
    erster = _tag(jetzt, zone) - timedelta(days=FENSTER_TAGE)
    return datetime.combine(erster, time.min, tzinfo=zone)


def _fenster_ende(jetzt: datetime) -> datetime:
    zone = _zone(jetzt)
    return datetime.combine(_tag(jetzt, zone) + timedelta(days=1), time.min, tzinfo=zone)


def _bestand_sql(alias: str) -> str:
    # Nur die Bestandsaufnahme hat sie geholt; hat auch der laufende Abruf sie gebracht, ist sie neue Post.
    return (f"EXISTS (SELECT 1 FROM mail_intake_items h WHERE h.episode_id={alias}.id AND h.lane='history') "
            f"AND NOT EXISTS (SELECT 1 FROM mail_intake_items l WHERE l.episode_id={alias}.id AND l.lane='live')")


def _regel_sql(alias: str) -> str:
    """Die Regel als Bedingung; Parameter: Beginn, Ende, Beginn, Ende (ISO)."""
    return (f"(({alias}.occurred_at IS NOT NULL AND julianday({alias}.occurred_at) >= julianday(?) "
            f"AND julianday({alias}.occurred_at) < julianday(?)) "
            f"OR ({alias}.occurred_at IS NULL AND julianday({alias}.recorded_at) >= julianday(?) "
            f"AND julianday({alias}.recorded_at) < julianday(?) AND NOT ({_bestand_sql(alias)})))")


def _von_aussen_sql(alias: str) -> str:
    from .episodes import EIGENE_HERKUNFT
    liste = ",".join(f"'{art}'" for art in EIGENE_HERKUNFT)
    return (f"COALESCE(json_extract({alias}.document, '$.provenance.source_type'), '') NOT IN ({liste}) "
            f"AND substr(COALESCE(json_extract({alias}.document, '$.provenance.source_ref'), ''), 1, 7) != 'upload:'")


def _parameter(jetzt: datetime) -> tuple[str, str, str, str]:
    beginn, ende = fenster_beginn(jetzt).isoformat(), _fenster_ende(jetzt).isoformat()
    return beginn, ende, beginn, ende


def aus_bestandsaufnahme(episodes, episode_ids: Iterable[str]) -> set[str]:
    """Welche dieser Quellen nur die Bestandsaufnahme eines Postfachs geholt hat."""
    ids = [i for i in dict.fromkeys(episode_ids) if i]
    if not ids:
        return set()
    platz = ",".join("?" for _ in ids)
    with episodes._lock:
        zeilen = episodes._conn.execute(
            f"SELECT e.id FROM episodes e WHERE e.id IN ({platz}) AND {_bestand_sql('e')}", ids).fetchall()
    return {zeile[0] for zeile in zeilen}


def neue_quellen(episodes, *, jetzt: datetime, limit: int = MAX_KANDIDATEN) -> list[str]:
    """Kennungen neuer Quellen von außen mit vollständigem Quellenbericht, die jüngste zuerst (nach Quelldatum,
    sonst nach Erfassung).

    Die Auswahl geschieht vor jeder Begrenzung: Nach dem Einlesen von Tausenden Mails desselben Tages verdrängt der
    Altbestand so keine wirklich neue Mail aus den ersten Plätzen.
    """
    from .episodes import sql_sichtbar
    sql = (f"SELECT e.id FROM episodes e WHERE {sql_sichtbar('e')} AND {_von_aussen_sql('e')} AND {_regel_sql('e')} "
           "AND EXISTS (SELECT 1 FROM working_memory_sources s JOIN working_memory_items i "
           "ON i.episode_id=s.episode_id AND i.fingerprint=s.fingerprint "
           "WHERE s.episode_id=e.id AND s.status='complete') "
           "ORDER BY julianday(COALESCE(e.occurred_at, e.recorded_at)) DESC, e.id DESC LIMIT ?")
    with episodes._lock:
        zeilen = episodes._conn.execute(sql, (*_parameter(jetzt), limit)).fetchall()
    return [zeile[0] for zeile in zeilen]


def anzahl_neu_von_aussen(episodes, *, jetzt: datetime) -> int:
    """Wie `EpisodeStore.neue_von_aussen`, aber nur, was nach der Regel neu ist (ungesichtet, von außen)."""
    from .episodes import EpisodeState
    sql = (f"SELECT COUNT(*) FROM episodes e WHERE e.state = ? AND {_von_aussen_sql('e')} AND {_regel_sql('e')}")
    with episodes._lock:
        zeile = episodes._conn.execute(sql, (EpisodeState.NEW.value, *_parameter(jetzt))).fetchone()
    return int(zeile[0])


__all__ = ['FENSTER_TAGE', 'anzahl_neu_von_aussen', 'aus_bestandsaufnahme', 'fenster_beginn', 'im_fenster', 'ist_neu',
           'neue_quellen']
