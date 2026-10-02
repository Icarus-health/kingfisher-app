"""Verdrahtung des Morgenbriefings: Termine heute und morgen, vorbereitet ohne Klick.

`GET /api/v1/tag/briefing` liefert

* `tageslage`: drei bis fünf Zeilen (`tagesbriefing.py`), jede mit ihren Aktionen,
* `termine`: jeder Termin heute und morgen, mit bekannten Teilnehmern vorbereitet
  (`terminvorbereitung.py`), samt Weg (`wegezeit.py`) und Packliste,
* `fristen`: die Fristen der nächsten sieben Tage und verstrichene, vermutlich offene Zusagen
  (`fristlage.py`), nach Dringlichkeit,
* `geburtstage`: Geburtstage heute und morgen, nur bestätigter innerer Kreis mit angenommenem Geburtstag
  (`wiederkehrendes.im_briefing`).

Alles wird aus den Akten gelesen; nichts wird angelegt oder verändert. Der Weg braucht die
Einwilligung „Fahrzeiten berechnen“ (`wegezeit_routes.py`); ohne sie steht dort ehrlich „Fahrzeit unbekannt“.
Ein Fehler in einem Teil (Kalender, Akten, Wetter) kostet nur diesen Teil und steht als `fehler` daneben.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from . import fristlage, identitaet, tagesbriefing, terminvorbereitung, wegezeit, wiederkehrendes
from .akten_routes import bausteine, nachfuehren
from .logbuch_routes import zeilen as logbuch_zeilen
from .model import user_timezone
from .wegezeit_routes import dienst as wegezeit_dienst
from .welt_briefing_routes import dienst as welt_dienst
from .wetter import gleicher_ort, ortsname
from .wetter_routes import dienst as wetter_dienst

logger = logging.getLogger(__name__)



def _jetzt() -> datetime:
    zone = user_timezone()
    return datetime.now(zone) if zone else datetime.now().astimezone()


def _wetter(app) -> dict[str, Any] | None:
    """Wetter am Wohnort (nur mit eingeschaltetem „Wetter im Briefing“, `wetter.py`); der Dienst merkt sich die
    Antwort 30 Minuten und stellt ohne Einwilligung keine Anfrage."""
    try:
        return wetter_dienst(app).aktuell()
    except Exception:  # noqa: BLE001 - Wetter ist Beiwerk
        logger.exception('Wetter konnte nicht bestimmt werden')
        return None


def wetter_am_termin(app, vorbereitungen: list[terminvorbereitung.Vorbereitung], jetzt: datetime) -> dict[str, Any] | None:
    """Das Wetter am Ort und zur Zeit des nächsten auswärtigen Termins (nicht am Wohnort, nicht online).

    Nur der Ortsname geht hinaus (`wetter.ortsname`), nie Straße, Titel oder Teilnehmer. Ist der Ort nicht
    aufzulösen oder der Dienst stumm, fehlt die Angabe.
    """
    dienst = wetter_dienst(app)
    einst = dienst.einstellung()
    if not einst.aktiv:
        return None
    for v in sorted((v for v in vorbereitungen if not v.termin.ganztaegig and v.termin.beginn >= jetzt),
                    key=lambda v: v.termin.beginn):
        ort = wegezeit.ort_bereinigt(v.termin.ort)
        name = ortsname(ort)
        if not name or gleicher_ort(name, einst.name):
            continue
        wetter = dienst.am_ort(ort, v.termin.beginn)
        return {'ort': wetter['ort'], 'wann': v.termin.beginn, 'wetter': wetter} if wetter else None
    return None


def _welt(app) -> dict[str, Any] | None:
    """Die Meldung des Tages aus der Welt, wenn es eine gibt. Liest nur; Abrufe laufen im Hintergrund."""
    try:
        return welt_dienst(app).heute()
    except Exception:  # noqa: BLE001 - Welt ist Beiwerk
        logger.exception('Weltmeldung konnte nicht gelesen werden')
        return None


def termine(app, jetzt: datetime) -> list[dict[str, Any]]:
    """Die Termine von heute und morgen (ohne bereits Beendete von heute) aus dem verbundenen Kalender."""
    kalender = getattr(app.state, 'calendar', None)
    if kalender is None:
        return []
    anfang = jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    gefunden = [e.to_dict() for e in kalender.events(days=3, at=anfang.astimezone(timezone.utc))]
    ergebnis = []
    for item in gefunden:
        try:
            beginn = datetime.fromisoformat(str(item['start'])).astimezone(jetzt.tzinfo)
            ende = datetime.fromisoformat(str(item.get('end') or item['start'])).astimezone(jetzt.tzinfo)
        except (KeyError, ValueError):
            continue
        tage = (beginn.date() - jetzt.date()).days
        if 0 <= tage <= 1 and ende >= jetzt:
            ergebnis.append({**item, 'start': beginn.isoformat(), 'end': ende.isoformat()})
    return sorted(ergebnis, key=lambda e: e['start'])


def vorbereiten_alle(app, jetzt: datetime, eintraege: list[dict[str, Any]]) -> list[terminvorbereitung.Vorbereitung]:
    """Jeder Termin mit Teilnehmern vorbereitet, dazu der Weg. Ein Fehler kostet nur diesen Termin."""
    _, akten = bausteine(app)
    eigene = identitaet.eigene_adressen(getattr(app.state, 'settings', None))
    fahrdienst = wegezeit_dienst(app)
    frist = fahrdienst.frist()   # ein Zeitbudget für alle Wege dieses Aufrufs; der Rest wird im Hintergrund nachgeholt
    ergebnis = []
    for eintrag in eintraege:
        episode_id, notiz = terminvorbereitung.termin_im_gedaechtnis(
            app.state.episodes, str(eintrag.get('uid') or ''), str(eintrag.get('source_id') or ''))
        termin = terminvorbereitung.Termin.aus_dict(eintrag, notiz=notiz, episode_id=episode_id)
        if termin is None:
            continue
        try:
            vorbereitung = terminvorbereitung.vorbereiten(termin, akten=akten, episodes=app.state.episodes,
                                                          eigene=eigene, jetzt=jetzt,
                                                          workspace=getattr(app.state, 'workspace', None))
        except Exception:  # noqa: BLE001 - der Termin bleibt sichtbar, nur ohne Vorbereitung
            logger.exception('Termin konnte nicht vorbereitet werden')
            vorbereitung = terminvorbereitung.Vorbereitung(termin=termin)
        if not termin.ganztaegig:
            try:
                vorheriger = wegezeit.vorheriger_termin(eintraege, eintrag)
                vorbereitung.wegezeit = fahrdienst.auskunft(termin.ort, beginn=termin.beginn, vorheriger=vorheriger,
                                                            frist_bis=frist).to_dict()
            except Exception:  # noqa: BLE001
                logger.exception('Weg konnte nicht bestimmt werden')
        ergebnis.append(vorbereitung)
    return ergebnis


def briefing(app, *, buchen: bool = True) -> dict[str, Any]:
    jetzt = _jetzt()
    ergebnis: dict[str, Any] = {'jetzt': jetzt.isoformat(), 'tageslage': None, 'termine': [], 'fristen': [],
                                'geburtstage': [], 'fehler': {}}
    eigene = identitaet.eigene_adressen(getattr(app.state, 'settings', None))
    try:
        nachfuehren(app)
    except Exception:  # noqa: BLE001
        logger.exception('Bezüge konnten nicht nachgeführt werden')
    vorbereitungen: list[terminvorbereitung.Vorbereitung] = []
    try:
        vorbereitungen = vorbereiten_alle(app, jetzt, termine(app, jetzt))
    except Exception as exc:  # noqa: BLE001
        ergebnis['fehler']['termine'] = 'Die Termine sind gerade nicht erreichbar.'
        logger.warning('Termine für das Tagesbriefing nicht lesbar: %s', type(exc).__name__)
    fristen: list[fristlage.Frist] = []
    try:
        bezuege, akten = bausteine(app)
        fristen = fristlage.sammeln(akten, bezuege, jetzt=jetzt, eigene=eigene)
    except Exception:  # noqa: BLE001
        logger.exception('Fristen konnten nicht gelesen werden')
        ergebnis['fehler']['fristen'] = 'Die Fristen sind gerade nicht lesbar.'
    geburtstage: list[dict[str, Any]] = []
    try:
        bezuege, _ = bausteine(app)
        geburtstage = wiederkehrendes.im_briefing(app.state.episodes, app.state.claims, bezuege.beschriftungen, jetzt)
    except Exception:  # noqa: BLE001
        logger.exception('Geburtstage konnten nicht gelesen werden')
    termin_wetter = None
    try:
        termin_wetter = wetter_am_termin(app, vorbereitungen, jetzt)
    except Exception:  # noqa: BLE001
        logger.exception('Wetter am Termin konnte nicht bestimmt werden')
    lage = tagesbriefing.erstellen(vorbereitungen, fristen, _wetter(app), jetzt=jetzt,
                                   termin_wetter=termin_wetter, welt=_welt(app), verlauf=logbuch_zeilen(app, jetzt, buchen=buchen),
                                   geburtstage=geburtstage)
    ergebnis['tageslage'] = lage.to_dict()
    ergebnis['termine'] = [v.to_dict() for v in vorbereitungen]
    ergebnis['fristen'] = [f.to_dict() for f in fristen]
    ergebnis['geburtstage'] = geburtstage
    ergebnis['wegezeit'] = wegezeit_dienst(app).stand()
    return ergebnis


def register(app, guard) -> None:
    @app.get('/api/v1/tag/briefing', dependencies=guard)
    def tag_briefing(nachladen: bool = False) -> dict[str, Any]:
        """`nachladen`: das stille Erneuern der Oberfläche bei offenem Tab; es zählt nicht als Blick (`logbuch_routes.zeilen`)."""
        return briefing(app, buchen=not nachladen)


__all__ = ['briefing', 'register', 'termine', 'vorbereiten_alle', 'wetter_am_termin']

