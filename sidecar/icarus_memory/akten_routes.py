"""Verdrahtung der Akten und Bezüge: Routen, Aufgabenbezug, Abgleich im Hintergrund.

Die Regeln stehen in `bezuege.py` (Quelle -> Sache) und `akten.py` (Sache ->
Akte). Hier steht nur, wie der Server sie mit seinen Speichern verbindet:

* `GET  /api/v1/akten/sachen`: alle Sachen mit Anzahl und letzter Aktivität.
* `GET  /api/v1/akten/akte?sache=…`: die Akte einer Sache.
* `GET  /api/v1/akten/quellen/{episode_id}`: die Bezüge einer Quelle.
* `PUT  /api/v1/akten/quellen/{episode_id}/zuordnung`: „gehört dazu“ oder „gehört
  nicht dazu“ (maßgeblich, umkehrbar).
* `DELETE /api/v1/akten/quellen/{episode_id}/zuordnung?sache=…`: Entscheidung zurücknehmen.
* `POST /api/v1/akten/aktualisieren`: Bezüge neu bestimmen (der Server tut es
  von selbst; diese Route dient Prüfung und Diagnose).

Die Bezüge werden bei jeder Anfrage kurz nachgeführt (höchstens `FRIST_S`
Sekunden); was dann noch fehlt, rechnet ein Hintergrundfaden zu Ende. Die
Antwort nennt, wie viele Quellen noch nicht berechnet sind (`berechnung.offen`),
statt zu tun, als wäre alles da.

Die Sachen-ID steht immer als Abfrageparameter oder im Körper, nie im Pfad:
Adressen und Namen enthalten Zeichen, die im Pfad Ärger machen.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from . import personen
from .akten import Akten
from .bezuege import ART_TEXT, ARTEN, Bezuege, zerlegen

logger = logging.getLogger(__name__)

#: Wie lange eine Anfrage höchstens auf die Nachführung der Bezüge wartet.
FRIST_S = 1.5
#: Wie oft eine neue Antwort die Bezüge nachführt (Sekunden); eine Mail von eben fehlt der Akte höchstens so lange.
NACHFUEHREN_ABSTAND_S = 3.0


class ZuordnungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sache: str = Field(min_length=3, max_length=300)
    aktion: Literal['zu', 'nicht']


def bausteine(app) -> tuple[Bezuege, Akten]:
    """Bezüge und Akten dieser App, an den aktuellen Speicher gebunden.

    Wird der Episodenspeicher ausgetauscht (Wiederherstellung, Tests), entstehen
    beide neu: Sie halten nur Zwischenwerte, keine eigenen Daten.
    """
    vorhanden = getattr(app.state, 'akten_bausteine', None)
    if vorhanden is not None and vorhanden[0] is app.state.episodes:
        return vorhanden[1], vorhanden[2]
    from . import identitaet
    bezuege = Bezuege(app.state.episodes, workspace=getattr(app.state, 'workspace', None),
                      eigene=lambda: identitaet.eigene_adressen(getattr(app.state, 'settings', None)))
    akten = Akten(app.state.episodes, bezuege, claims=getattr(app.state, 'claims', None),
                  aufgaben=lambda sache, ids: aufgaben_zu(app, bezuege, sache, ids))
    app.state.akten_bausteine = (app.state.episodes, bezuege, akten)
    return bezuege, akten


def aufgaben_zu(app, bezuege: Bezuege, sache: str, ids: list[str]) -> list[Any]:
    """Aufgaben, die zu einer Sache gehören: des Projekts, bei der die Person liegt, oder aus ihren Quellen."""
    tasks = getattr(app.state, 'tasks', None)
    if tasks is None:
        return []
    gefunden: dict[str, Any] = {}
    art, kennung = zerlegen(sache) or ('', '')
    if art == 'projekt' and not kennung.startswith('n:'):
        gefunden.update({t.id: t for t in tasks.by_project(kennung, include_closed=True)})
    elif art == 'person':
        name = bezuege.beschriftung(sache)
        gefunden.update({t.id: t for t in tasks.open_tasks(limit=None) if personen.wartet_auf(t, name)})
    quellen = {f'episode:{i}' for i in ids}
    if quellen:
        gefunden.update({t.id: t for t in tasks.all_tasks(limit=500)
                         if (t.provenance.source_ref or '') in quellen})
    return list(gefunden.values())


#: Schützt nur das Prüfen und Starten des Hintergrundfadens (kurz gehalten, nie über Rechenarbeit).
_FADEN_SPERRE = threading.Lock()


def _ins_logbuch(app, bezuege: Bezuege) -> None:
    """Hält neue und veränderte Akten im Logbuch fest (`logbuch.py`). Ein Fehler hier stört nie."""
    try:
        buch = getattr(app.state, 'logbuch', None)
        if buch is None:
            return
        sachen = bezuege.sachen(limit=5000)['sachen']
        namen = bezuege.beschriftungen([s['sache'] for s in sachen])
        buch.akten_abgleichen([{**s, 'name': namen[s['sache']]} for s in sachen])
    except Exception:  # noqa: BLE001
        logger.exception('Logbuch: Akten konnten nicht abgeglichen werden')


def nachlauf_anmelden(app, faellig: Callable[[], bool], ausfuehren: Callable[[], Any]) -> None:
    """Meldet eine Arbeit an, die im Hintergrundfaden nach dem Abgleich der Bezüge läuft (etwa der Lint).

    `faellig` muss billig sein (es wird bei jeder Nachführung gefragt) und selbst drosseln;
    `ausfuehren` läuft im selben Faden wie der Abgleich, also nie parallel zu ihm.
    """
    nachlauf = getattr(app.state, 'akten_nachlauf', None)
    if nachlauf is None:
        nachlauf = app.state.akten_nachlauf = []
    nachlauf.append((faellig, ausfuehren))


def _faellige_nachlaeufe(app) -> list[Callable[[], Any]]:
    faellig = []
    for pruefen, ausfuehren in getattr(app.state, 'akten_nachlauf', None) or ():
        try:
            if pruefen():
                faellig.append(ausfuehren)
        except Exception:  # noqa: BLE001 - ein kaputter Nachlauf hält die Akten nie auf
            continue
    return faellig


def nachfuehren(app, *, warten: bool = False) -> dict[str, Any]:
    """Führt die Bezüge nach. Kurz und begrenzt; den Rest übernimmt ein Hintergrundfaden.

    `warten` rechnet alles in dieser Anfrage zu Ende (Prüfung und Diagnose). Danach darf „Akten als Ordner“
    schreiben (`akten_export_routes.anstossen`), sobald alle Bezüge berechnet sind. Angemeldete
    Nachläufe (`nachlauf_anmelden`, etwa der Lint) laufen, wenn sie fällig sind, im selben Hintergrundfaden
    nach dem Abgleich, nie in der Anfrage selbst.
    """
    stand = _nachfuehren(app, warten=warten)
    anstossen = getattr(app.state, 'akten_export_anstossen', None)
    if anstossen is not None and not stand['offen']:
        try:
            anstossen()
        except Exception:  # noqa: BLE001 - der Ordner ist Beiwerk; er darf nie eine Anfrage kippen
            pass
    return stand


def _nachfuehren(app, *, warten: bool = False) -> dict[str, Any]:
    bezuege, _ = bausteine(app)
    stand = {'offen': 0, 'berechnet': 0}
    geprueft = getattr(app.state, 'akten_geprueft', None)
    unveraendert = (not warten and geprueft is not None and geprueft[0] is bezuege
                    and geprueft[1] == bezuege.aenderungsstand())
    if not unveraendert:
        stand = bezuege.aktualisieren() if warten else bezuege.aktualisieren(frist_s=FRIST_S)
        if stand['berechnet']:
            _ins_logbuch(app, bezuege)
        if not stand['offen']:
            # Der Stand nach dem Abgleich: Wer ihn unverändert wiedersieht, muss nicht noch einmal nachsehen.
            app.state.akten_geprueft = (bezuege, bezuege.aenderungsstand())
    nachlaeufe = [] if warten else _faellige_nachlaeufe(app)
    if (stand['offen'] or nachlaeufe) and not warten:
        # Prüfen und Starten unter einer Sperre: Zwei gleichzeitige Anstöße (zwei Anfragen, Frage und
        # Anzeige) dürfen nicht beide „kein Faden läuft“ sehen und zwei Neuaufbauten parallel starten.
        with _FADEN_SPERRE:
            faden = getattr(app.state, 'akten_faden', None)
            if faden is None or not faden.is_alive():
                offen = bool(stand['offen'])

                def arbeiten() -> None:
                    from .hintergrund import niedrige_prioritaet
                    niedrige_prioritaet()  # Rechenarbeit ohne Modell; die Antworten der API gehen vor
                    try:
                        if offen and bezuege.aktualisieren()['berechnet']:
                            _ins_logbuch(app, bezuege)
                        for ausfuehren in (nachlaeufe if not offen else _faellige_nachlaeufe(app)):
                            ausfuehren()
                    except Exception:  # noqa: BLE001 - der nächste Aufruf versucht es erneut, nichts bricht ab
                        pass
                faden = threading.Thread(target=arbeiten, name='akten-bezuege', daemon=True)
                app.state.akten_faden = faden
                faden.start()
    return {'offen': stand['offen'], 'berechnet': stand['berechnet']}


def _mit_namen(bezuege: Bezuege, daten: dict[str, Any]) -> dict[str, Any]:
    """Bezüge einer Quelle mit lesbaren Namen und den Textstellen als Zitat."""
    episode_id = daten['episode_id']
    for eintrag in daten['bezuege']:
        eintrag['name'] = bezuege.beschriftung(eintrag['sache'])
        eintrag['art_text'] = ART_TEXT.get(eintrag['art'], eintrag['art'])
        eintrag['zitate'] = [z for z in (bezuege.zitat(episode_id, s['start'], s['ende']) for s in eintrag['stellen']) if z][:3]
    for offen in daten['offen']:
        offen['zitat'] = bezuege.zitat(episode_id, offen['stelle']['start'], offen['stelle']['ende']) if offen['stelle'] else ''
        offen['art_text'] = ART_TEXT.get(offen['art'], offen['art'])
        offen['kandidaten'] = [{'sache': k, 'name': bezuege.beschriftung(k)} for k in offen['kandidaten']]
    for abgelehnt in daten['abgelehnt']:
        abgelehnt['name'] = bezuege.beschriftung(abgelehnt['sache'])
    return daten


def verbinden(app) -> None:
    """Gibt dem Speicher der Episoden den Zugang zu den Akten (für „Suchen von oben“, `akten_kontext.py`).

    `akten_zugang` liefert die Akten ohne Rechenarbeit (auch beim Anzeigen alter Antworten);
    `akten_aktualisieren` führt die Bezüge kurz nach und läuft nur, wenn eine neue Antwort vorbereitet wird.
    Beides hängt am Speicher, den der Server gerade hat, und folgt ihm, wenn er ausgetauscht wird.
    """
    episodes = app.state.episodes
    letzte = [float('-inf')]

    def aktualisieren() -> None:
        # Höchstens alle NACHFUEHREN_ABSTAND_S Sekunden: Schon das Nachsehen kostet eine Abfrage über den Bestand,
        # und jede Frage schreibt (Zwischenspeicher der Akten), sodass der Schnellweg von `nachfuehren` nie greift.
        if app.state.episodes is episodes and time.monotonic() - letzte[0] >= NACHFUEHREN_ABSTAND_S:
            letzte[0] = time.monotonic()
            nachfuehren(app)

    episodes.akten_zugang = lambda: bausteine(app)[1] if app.state.episodes is episodes else None
    episodes.akten_aktualisieren = aktualisieren


def register(app, guard) -> None:
    verbinden(app)

    @app.get('/api/v1/akten/sachen', dependencies=guard)
    def akten_sachen(art: str | None = Query(None), suche: str = Query('', max_length=200),
                     limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                     warten: bool = False) -> dict[str, Any]:
        """Sachen mit Anzahl der Quellen und letzter Aktivität, jüngste zuerst, mit Gesamtzahl."""
        if art is not None and art not in ARTEN:
            raise HTTPException(status_code=422, detail='Unbekannte Art einer Sache.')
        berechnung = nachfuehren(app, warten=warten)
        bezuege, _ = bausteine(app)
        seite = bezuege.sachen(art=art, suche=suche, limit=limit, offset=offset)
        namen = bezuege.beschriftungen([e['sache'] for e in seite['sachen']])
        for eintrag in seite['sachen']:
            eintrag['art_text'] = ART_TEXT[eintrag['art']]
            eintrag['name'] = namen[eintrag['sache']]
        return {**seite, 'berechnung': berechnung}

    @app.get('/api/v1/akten/akte', dependencies=guard)
    def akte(sache: str = Query(..., min_length=3, max_length=300), alle: bool = False,
             warten: bool = False) -> dict[str, Any]:
        """Die Akte einer Sache: Lage (falls vorhanden), Verlauf, Offen, Fristen, Stand, Beteiligte, Termine, Aufgaben."""
        if zerlegen(sache) is None:
            raise HTTPException(status_code=422, detail='Ungültige Sache.')
        berechnung = nachfuehren(app, warten=warten)
        _, akten = bausteine(app)
        daten = akten.akte(sache, alle=alle)
        if daten is None:
            raise HTTPException(status_code=404, detail='Zu dieser Sache gibt es (noch) keine Quellen.')
        daten['berechnung'] = berechnung
        # Ebene 3: die Lage, falls eine da ist. Ohne Modell ist sie None, die Akte ist trotzdem vollständig.
        from .lage_routes import lagen_von
        lagen = lagen_von(app)
        daten['lage'] = lagen.lage(sache, daten)
        # Zeigt die veraltete Lage nichts mehr (alles überholt), weiß die Oberfläche trotzdem, dass eine neue kommt.
        daten['lage_wird_aktualisiert'] = daten['lage'] is None and lagen.ausstehend(sache, daten)
        return daten

    @app.get('/api/v1/akten/quellen/{episode_id}', dependencies=guard)
    def akten_quelle(episode_id: str) -> dict[str, Any]:
        """Die Bezüge einer Quelle: Sachen mit Grundlage, offene Erwähnungen mit Kandidaten."""
        nachfuehren(app)
        bezuege, _ = bausteine(app)
        daten = bezuege.bezuege_der_quelle(episode_id)
        if daten is None:
            raise HTTPException(status_code=404, detail='Die Quelle gibt es nicht oder sie gilt nicht mehr.')
        return _mit_namen(bezuege, daten)

    @app.put('/api/v1/akten/quellen/{episode_id}/zuordnung', dependencies=guard)
    def akten_zuordnen(episode_id: str, body: ZuordnungIn) -> dict[str, Any]:
        """Setzt die Entscheidung des Nutzers: `zu` (gehört dazu) oder `nicht` (gehört nicht dazu)."""
        bezuege, _ = bausteine(app)
        try:
            daten = bezuege.nutzer_setzen(episode_id, body.sache, body.aktion)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _mit_namen(bezuege, daten)

    @app.delete('/api/v1/akten/quellen/{episode_id}/zuordnung', dependencies=guard)
    def akten_zuordnung_entfernen(episode_id: str, sache: str = Query(..., min_length=3, max_length=300)) -> dict[str, Any]:
        """Nimmt die Entscheidung des Nutzers zurück; danach gilt wieder, was das Programm fand."""
        bezuege, _ = bausteine(app)
        if not bezuege.nutzer_entfernen(episode_id, sache):
            raise HTTPException(status_code=404, detail='Dazu gibt es keine Entscheidung von dir.')
        daten = bezuege.bezuege_der_quelle(episode_id)
        return _mit_namen(bezuege, daten) if daten else {'episode_id': episode_id, 'bezuege': [], 'offen': [],
                                                         'abgelehnt': [], 'veraltet': [], 'berechnet': False}

    @app.post('/api/v1/akten/aktualisieren', dependencies=guard)
    def akten_aktualisieren(max_quellen: int | None = Query(None, ge=1)) -> dict[str, int]:
        """Bestimmt die Bezüge neu (Prüfung und Diagnose); der Server tut es sonst von selbst."""
        bezuege, _ = bausteine(app)
        return bezuege.aktualisieren(max_quellen=max_quellen)
