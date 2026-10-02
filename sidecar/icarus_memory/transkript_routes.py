"""Verdrahtung des Transkript-Eingangs: Ordner, Zuordnung, Auskunft.

Die Regeln stehen in `transkript_eingang.py` (Lesen) und
`transkript_zuordnung.py` (Termin und Sprecher). Der Ordner läuft über
dieselbe Route wie der Dokumentenordner (`folder_sync.py`, `Ordnerart`), mit
eigener Einstellung `transcript_sync`. Hier steht, was nur für Mitschriften
gilt:

* **Ordner wählen** ohne Tippen. Die Oberfläche bittet um eine Auswahl
  (`POST /api/v1/transkripte/ordner`), der Mac-Helfer öffnet den Auswahldialog
  auf dem Rechner und meldet den gewählten Ordner zurück. Der Server kann den
  Helfer nur bitten, einen Dialog zu zeigen, nie, einen Pfad zu öffnen. Die
  Wahl im Dialog ist die Freigabe dieses einen Ordners.
* **Trennen** entzieht alle Mitschriften des Ordners sofort und lässt den
  Helfer seinen alten Ordner nicht wieder anbieten.
* **Zuordnung** zu Terminen: Auskunft, Klick auf einen Vorschlag, Lösen.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

from . import identitaet
from .episodes import EpisodeError
from .folder_sync import Ordnerart, now, register_folder_routes
from .transkript_zuordnung import Zuordner, Zuordnungen

TRANSKRIPTE = Ordnerart(prefix='/api/v1/transcript-sync', einstellung='transcript_sync',
                        schluessel='transkript', herkunft='mac-transkript', transkripte=True,
                        vorgabe_name='Transkripte')

VORGABE = 'Dokumente/Kingfisher/Transkripte'
"""Der vorgeschlagene Ordner, so wie der Nutzer ihn kennt (Dokumente-Ordner des Nutzers)."""


class OrdnerIn(BaseModel):
    modus: Literal['vorgabe', 'waehlen']


class ZuordnungIn(BaseModel):
    termin: str = Field(min_length=3, max_length=4096)


def register_transkript_routes(app, guard, data_dir) -> None:
    app.state.zuordnungen = Zuordnungen(data_dir() / 'gespraeche.sqlite3')   # nach einer Wiederherstellung neu geöffnet

    def zuordner() -> Zuordner:
        """Der Zuordner zum aktuellen Episodenbestand (der wird nach einer Wiederherstellung ersetzt)."""
        aktuell = getattr(app.state, 'zuordner', None)
        if aktuell is None or aktuell.episodes is not app.state.episodes or aktuell.ablage is not app.state.zuordnungen:
            aktuell = Zuordner(app.state.episodes, app.state.zuordnungen,
                               eigene=lambda: identitaet.eigene_adressen(getattr(app.state, 'settings', None)),
                               termin_projekt=lambda uid: app.state.workspace.event_project(uid))
            app.state.zuordner = aktuell
        return aktuell

    zuordner()
    app.state.zuordner_holen = zuordner
    ordner = register_folder_routes(app, guard, data_dir, TRANSKRIPTE)

    @app.get('/api/v1/transkripte', dependencies=guard)
    def uebersicht(limit: int = Query(100, ge=1, le=500)) -> dict[str, Any]:
        """Ordner, Zähler und die Mitschriften (neueste zuerst) mit ihrem Stand."""
        with app.state.conversation_lock:
            z = zuordner()
            z.nachziehen()
            eintraege, stand = z.eintraege(limit=limit)
            return {'ordner': ordner.public(), 'vorgabe': VORGABE, 'stand': stand, 'eintraege': eintraege,
                    'mehr': stand['aufgenommen'] > len(eintraege)}

    @app.post('/api/v1/transkripte/ordner', dependencies=guard)
    def ordner_waehlen(body: OrdnerIn) -> dict[str, Any]:
        """Bittet den Mac-Helfer, den Auswahldialog zu zeigen (oder den Vorgabeordner anzulegen)."""
        with app.state.conversation_lock:
            s = ordner.state()
            s['pick_request'] = {'id': uuid.uuid4().hex, 'modus': body.modus, 'at': now().isoformat()}
            ordner.save(s)
            return ordner.public()

    @app.delete('/api/v1/transkripte/ordner/auswahl', dependencies=guard)
    def auswahl_abbrechen() -> dict[str, Any]:
        with app.state.conversation_lock:
            s = ordner.state()
            s.pop('pick_request', None)
            ordner.save(s)
            return ordner.public()

    @app.delete('/api/v1/transkripte/ordner', dependencies=guard)
    def ordner_trennen() -> dict[str, Any]:
        """Trennt den Ordner und entzieht alle seine Mitschriften. Die Originaldateien bleiben unberührt."""
        with app.state.conversation_lock:
            s = ordner.state()
            entzogen = len(s['files'])
            ordner.entziehen(s)
            ordner.save({'enabled': False, 'generation': int(s.get('generation') or 0) + 1, 'root_id': None,
                         'folder': None, 'files': {}, 'missing': [], 'digests': {}, 'synced_at': None,
                         'last_run': None, 'seen_at': s.get('seen_at'), 'getrennt': True})
            return {**ordner.public(), 'entzogen': entzogen}

    def _bekannt(episode_id: str):
        try:
            return app.state.episodes.get(episode_id)
        except EpisodeError as exc:
            raise HTTPException(status_code=404, detail='Diese Mitschrift ist nicht bekannt.') from exc

    @app.post('/api/v1/transkripte/{episode_id}/zuordnung', dependencies=guard)
    def zuordnung_setzen(episode_id: str, body: ZuordnungIn) -> dict[str, Any]:
        """Der Nutzer wählt den Termin: aus dem Vorschlag oder von Hand. Gilt, bis er es ändert."""
        _bekannt(episode_id)
        with app.state.conversation_lock:
            try:
                zuordner().bestaetigen(episode_id, body.termin)
            except EpisodeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            eintraege, _ = zuordner().eintraege(limit=500)
            return next(e for e in eintraege if e['id'] == episode_id)

    @app.delete('/api/v1/transkripte/{episode_id}/zuordnung', dependencies=guard)
    def zuordnung_loesen(episode_id: str) -> dict[str, Any]:
        """Nimmt die Zuordnung zurück; die Mitschrift steht danach für sich."""
        _bekannt(episode_id)
        with app.state.conversation_lock:
            try:
                zuordner().loesen(episode_id)
            except EpisodeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            eintraege, _ = zuordner().eintraege(limit=500)
            return next(e for e in eintraege if e['id'] == episode_id)

    @app.get('/api/v1/transkripte/termin', dependencies=guard)
    def zum_termin(key: str = Query(min_length=3, max_length=4096)) -> dict[str, Any]:
        """Die Mitschriften eines Termins und die, die noch zu keinem gehören."""
        return termin_stand(app, key)


def termin_stand(app, key: str | None) -> dict[str, Any]:
    """Was zu einem Termin gehört: zugeordnete Mitschriften und Angebote. Ein Fehler kostet nur diese Auskunft."""
    leer = {'transkripte': [], 'angebote': []}
    holen = getattr(app.state, 'zuordner_holen', None)
    if holen is None or not key:
        return leer
    try:
        z = holen()
        return {'transkripte': z.fuer_termin(key), 'angebote': z.angebote(key)}
    except Exception:  # noqa: BLE001
        return leer


def nach_aufnahme(app):
    """Der Rückruf des Ordneradapters: merkt die Zeichen einer Mitschrift und ordnet sie zu."""
    def melden(episode, hinweise: dict[str, Any]) -> None:
        holen = getattr(app.state, 'zuordner_holen', None)
        if holen is None:
            return
        try:
            holen().vormerken(episode, hinweise)
        except Exception:  # noqa: BLE001 - die Aufnahme darf daran nie scheitern; `nachziehen` holt es nach
            import logging
            logging.getLogger(__name__).exception('Mitschrift %s konnte nicht zugeordnet werden', episode.id)
    return melden


__all__ = ['TRANSKRIPTE', 'VORGABE', 'nach_aufnahme', 'register_transkript_routes', 'termin_stand']
