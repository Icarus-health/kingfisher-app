"""Verdrahtung des Microsoft-Zugangs: Anmeldung mit Code, Konten, Teams-Mitschriften im Hintergrund.

Ein Microsoft-Konto ist **eine** Anmeldung (`microsoft_anmeldung`) und daraus zwei gewöhnliche Zugänge in den
Einstellungen: ein Postfach (`auth_method = 'microsoft_graph'`) und ein Kalender (`kind = 'microsoft'`). Beide
teilen sich einen Eintrag im Schlüsselspeicher (`konto_schluessel(adresse)`); der verschwindet, wenn der letzte
Zugang des Kontos getrennt wird. Verbinden liest noch nichts ein, wie bei Google: Die Post kommt erst mit
„Mails einlesen“, der Kalender wie jeder andere Kalender.

Teams-Mitschriften holt ein eigener, langsamer Takt (`TAKT_S`), sobald ein Konto sie dazugenommen hat. Er tritt
zurück, wenn der Hintergrund gesperrt ist (pausiert, jemand arbeitet, eine Antwort entsteht), und legt jede
Mitschrift über denselben Weg ab wie der Transkript-Ordner.
"""
from __future__ import annotations

import copy
import json
import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import config
from .microsoft_anmeldung import (MITSCHRIFT_SCOPE, GRUENDE, MicrosoftAnmeldung, MicrosoftFehler,
                                  konto_schluessel, ms_request)
from .microsoft_graph import GraphClient, MicrosoftKalender, MicrosoftPost, Mitschriften, Postablage, graph_get

logger = logging.getLogger(__name__)

AUTH = 'microsoft_graph'
KALENDER = 'microsoft'
#: Der Takt der Teams-Mitschriften (Sekunden) und die Wartezeit nach dem Start.
TAKT_S = 600.0
ANLAUF_S = 30.0


class AnmeldenIn(BaseModel):
    adresse: str = Field(default='', max_length=320)
    mitschriften: bool = False


class ClientIn(BaseModel):
    client_id: str = Field(default='', max_length=64)


def ist_microsoft(entry: Any) -> bool:
    return getattr(entry, 'auth_method', '') == AUTH or getattr(entry, 'kind', '') == KALENDER


def ablage(app) -> Postablage:
    """Die Ablage der Nummern und Mitschriften im aktuellen Datenordner."""
    daten = getattr(app.state, 'microsoft_daten', None)
    if daten is None:
        from .server import _data_dir as daten
    pfad = Path(daten()) / 'microsoft.sqlite3'
    aktuell = getattr(app.state, 'microsoft_ablage', None)
    if aktuell is None or aktuell.pfad != pfad:
        aktuell = app.state.microsoft_ablage = Postablage(pfad)
    return aktuell


def client(app, adresse: str) -> GraphClient:
    # Beides wird erst beim Aufruf gelesen: Die Leser entstehen schon beim Start (`_build_agent`), bevor die Routen
    # und damit `app.state.microsoft` stehen; Tests und Browserprobe setzen `microsoft_graph_get` auf eine Attrappe.
    return GraphClient(lambda: app.state.microsoft.access_token(adresse),
                       request=lambda *a, **k: (getattr(app.state, 'microsoft_graph_get', None) or graph_get)(*a, **k))


def _schluesselspeicher(app) -> Any:
    anmeldung = getattr(app.state, 'microsoft', None)
    return anmeldung.keychain if anmeldung is not None else getattr(app.state, 'keychain', None)


def zugang_da(app, adresse: str) -> bool:
    """Liegt für das Konto ein Zugang im Schlüsselspeicher? Liest nur, ob er da ist, nie seinen Inhalt hinaus."""
    speicher = _schluesselspeicher(app)
    return bool(adresse and speicher is not None and speicher.available and speicher.get(konto_schluessel(adresse)))


def post_leser(app, entry: Any) -> MicrosoftPost | None:
    """Der Leser eines Microsoft-Postfachs für `_configured_mail`; ohne gespeicherten Zugang keiner."""
    if not zugang_da(app, entry.user):
        return None
    return MicrosoftPost(entry.user, client(app, entry.user), ablage(app))


def kalender_leser(app, entry: Any) -> MicrosoftKalender | None:
    if not zugang_da(app, entry.user):
        return None
    return MicrosoftKalender(client(app, entry.user))


def adressen(app) -> list[str]:
    """Die Adressen aller Microsoft-Konten in den Einstellungen (Post oder Kalender), ohne Doppelte."""
    settings = app.state.settings
    gesehen: dict[str, str] = {}
    for entry in [*settings.mail_accounts, *settings.calendar_sources]:
        if ist_microsoft(entry) and entry.user:
            gesehen.setdefault(entry.user.casefold(), entry.user)
    return list(gesehen.values())


def nach_entfernen(app, entfernt: Any) -> None:
    """Nach „Trennen“: Ist es der letzte Zugang dieses Microsoft-Kontos, verschwinden Zugang und Nummern."""
    if not ist_microsoft(entfernt) or not entfernt.user:
        return
    if entfernt.user.casefold() in {a.casefold() for a in adressen(app)}:
        return
    app.state.microsoft.vergessen(entfernt.user)
    try:
        ablage(app).vergessen(entfernt.user.casefold())
    except Exception:  # noqa: BLE001 - die Ablage enthält nur Nummern; der Zugang ist schon weg
        logger.exception('Microsoft-Ablage nicht aufgeräumt')


def mit_mitschriften(app, adresse: str) -> bool:
    zugang = app.state.microsoft.zugang(adresse) if adresse else None
    return bool(zugang and MITSCHRIFT_SCOPE in zugang['scopes'])


def ablegen_fuer(app):
    """Legt eine Teams-Mitschrift ab wie eine Datei aus dem Transkript-Ordner und stößt die Einordnung an."""
    def ablegen(transkript, source_key: str, ref: str):
        from . import logbuch, transkript_eingang
        from .model import Provenance, SourceType
        from .source_versions import track_source
        from .transkript_routes import nach_aufnahme
        herkunft = Provenance(source_type=SourceType.DOCUMENT, source_ref=ref, extracted_by='icarus/microsoft/teams',
                              captured_at=datetime.now().astimezone())
        with app.state.conversation_lock:
            episode, neu = transkript_eingang.aufnehmen(app.state.episodes, transkript, herkunft, source_key)
            # Wie beim Ordner: Der Schlüssel zeigt auf die aktuelle Fassung (eine geänderte Mitschrift ersetzt die alte).
            track_source(app.state.episodes, getattr(app.state, 'claims', None), source_key, episode)
            nach_aufnahme(app)(episode, transkript.hinweise())
        if neu:
            logbuch.vermerke('quellen', sorte='transkript', anzahl=1)
            planer = getattr(app.state, 'scheduler', None)
            if planer is not None:
                planer.request_working_memory(episode.id)
        return episode
    return ablegen


def mitschriften_holen(app) -> dict[str, Any]:
    """Ein Durchgang über alle Konten mit Mitschriften. Fehler eines Kontos kosten nur dieses Konto."""
    ergebnis = {}
    for adresse in adressen(app):
        if not mit_mitschriften(app, adresse):
            continue
        try:
            ergebnis[adresse] = Mitschriften(adresse, client(app, adresse), ablage(app), ablegen_fuer(app)).durchgang()
        except MicrosoftFehler as exc:
            ergebnis[adresse] = {'satz': exc.satz, 'grund': exc.grund}
        except Exception:  # noqa: BLE001
            logger.exception('Teams-Mitschriften nicht abgeholt')
            ergebnis[adresse] = {'satz': GRUENDE['unbekannt'], 'grund': 'unbekannt'}
    return ergebnis


def takt_starten(app) -> None:
    """Startet den Takt der Teams-Mitschriften, wenn ein Konto sie hat und er nicht schon läuft."""
    faden = getattr(app.state, 'microsoft_takt', None)
    if faden is not None and faden.is_alive():
        return
    if not any(mit_mitschriften(app, a) for a in adressen(app)):
        return
    halt = app.state.microsoft_halt

    def laufen() -> None:
        warten = ANLAUF_S
        while not halt.wait(warten):
            warten = TAKT_S
            steuerung = getattr(app.state, 'hintergrund', None)
            try:
                if steuerung is not None and steuerung.sperre():
                    warten = max(30.0, steuerung.wartezeit())
                    continue
                if not any(mit_mitschriften(app, a) for a in adressen(app)):
                    return
                mitschriften_holen(app)
            except Exception:  # noqa: BLE001 - ein Fehler darf den Takt nicht beenden
                logger.exception('Takt der Teams-Mitschriften')

    app.state.microsoft_takt = threading.Thread(target=laufen, name='microsoft-mitschriften', daemon=True)
    app.state.microsoft_takt.start()


def install_routes(app, guard, data_dir, rebuild) -> None:
    from .secrets import Keychain
    app.state.microsoft = MicrosoftAnmeldung(
        getattr(app.state, 'keychain', None) or Keychain(data_dir=data_dir()),
        request=lambda *a, **k: (getattr(app.state, 'microsoft_request', None) or ms_request)(*a, **k))
    app.state.microsoft_daten = data_dir
    app.state.microsoft_halt = threading.Event()
    anmeldung: MicrosoftAnmeldung = app.state.microsoft

    @app.get('/api/v1/microsoft/config', dependencies=guard)
    def stand() -> dict[str, Any]:
        return anmeldung.stand()

    @app.put('/api/v1/microsoft/config', dependencies=guard)
    def setzen(body: ClientIn) -> dict[str, Any]:
        try:
            anmeldung.client_setzen(body.client_id)
        except (MicrosoftFehler, ValueError) as exc:
            raise HTTPException(422, str(exc)) from None
        return anmeldung.stand()

    # Ob eine Adresse zu Microsoft 365 gehört, beantwortet die eine Anbieter-Erkennung
    # (`GET /api/v1/integrations/mail-providers/erkennen`, `anbieter_erkennen.py`); hier gibt es keinen zweiten Weg.

    @app.post('/api/v1/microsoft/anmelden', dependencies=guard)
    def anmelden(body: AnmeldenIn) -> Any:
        # Wie beim Kalender: `detail` ist der Satz für den Menschen, `grund` die Kennung für Oberfläche und Tests.
        try:
            return anmeldung.beginnen(body.adresse, body.mitschriften)
        except MicrosoftFehler as exc:
            return JSONResponse({'detail': exc.satz, 'grund': exc.grund}, status_code=exc.status)
        except ValueError as exc:
            return JSONResponse({'detail': str(exc), 'grund': 'zu_viele'}, status_code=429)

    def verbinden(sitzung: str) -> dict[str, Any]:
        """Speichert eine fertige Anmeldung: Zugang in den Schlüsselspeicher, Postfach und Kalender in die Einstellungen."""
        with app.state.conversation_lock, anmeldung.lock:
            try:
                eintrag = anmeldung.uebernehmen(sitzung)
            except ValueError:
                return {}
            adresse = eintrag['email']
            settings = app.state.settings
            original = copy.deepcopy(settings)
            schluessel = konto_schluessel(adresse)
            vorher = anmeldung.keychain.get(schluessel)
            try:
                anmeldung.keychain.set(schluessel, json.dumps(eintrag['grant']))
                neu = []
                if not any(e.auth_method == AUTH and e.user.casefold() == adresse.casefold() for e in settings.mail_accounts):
                    konto = config.MailAccountSettings(id='mail-' + uuid.uuid4().hex, label=adresse, user=adresse,
                                                       sender=adresse, imap_host='graph.microsoft.com', smtp_host='',
                                                       auth_method=AUTH)
                    settings.mail_accounts.append(konto)
                    neu.append('post')
                if not any(e.kind == KALENDER and e.user.casefold() == adresse.casefold() for e in settings.calendar_sources):
                    settings.calendar_sources.append(config.CalendarSourceSettings(
                        id='calendar-' + uuid.uuid4().hex, label=f'Outlook: {adresse}'[:120], kind=KALENDER, url='me',
                        user=adresse))
                    neu.append('kalender')
                config.save(data_dir(), settings)
            except Exception:
                app.state.settings = original
                if vorher:
                    anmeldung.keychain.set(schluessel, vorher)
                else:
                    anmeldung.keychain.delete(schluessel)
                raise
            anmeldung.tokens.pop(schluessel, None)
            eintrag.pop('grant', None)
            eintrag['status'] = 'connected'
            mitschriften = MITSCHRIFT_SCOPE in (anmeldung.zugang(adresse) or {}).get('scopes', [])
            post = next(e.id for e in settings.mail_accounts if e.auth_method == AUTH and e.user.casefold() == adresse.casefold())
        rebuild()
        if mitschriften:
            takt_starten(app)
        return {'neu': neu, 'mail_konto': post, 'mitschriften_an': mitschriften}

    @app.get('/api/v1/microsoft/anmelden/{sitzung}', dependencies=guard)
    def nachfragen(sitzung: str) -> dict[str, Any]:
        sicht = anmeldung.nachfragen(sitzung)
        if sicht is None:
            return {'status': 'expired', 'grund': 'abgelaufen', 'satz': GRUENDE['abgelaufen']}
        if sicht['status'] == 'ready':
            sicht = {**sicht, **verbinden(sitzung), 'status': 'connected'}
        return sicht

    @app.delete('/api/v1/microsoft/anmelden/{sitzung}', dependencies=guard)
    def abbrechen(sitzung: str) -> dict[str, Any]:
        anmeldung.abbrechen(sitzung)
        return {'status': 'cancelled'}

    @app.get('/api/v1/microsoft/konten', dependencies=guard)
    def konten() -> dict[str, Any]:
        settings = app.state.settings
        ergebnis = []
        for adresse in adressen(app):
            zugang = anmeldung.zugang(adresse)
            eigene = [e for e in [*settings.mail_accounts, *settings.calendar_sources]
                      if ist_microsoft(e) and e.user.casefold() == adresse.casefold()]
            besprechungen = []
            try:
                for zeile in ablage(app).mitschriften(adresse.casefold(), 10):
                    besprechungen.append({'titel': zeile['titel'], 'beginn': zeile['beginn'], 'stand': zeile['stand'],
                                          'satz': zeile['satz']})
            except Exception:  # noqa: BLE001 - die Auskunft ist Beiwerk
                logger.exception('Mitschriften nicht lesbar')
            ergebnis.append({
                'adresse': adresse, 'verbunden': zugang is not None,
                'post': any(getattr(e, 'auth_method', '') == AUTH for e in eigene),
                'kalender': any(getattr(e, 'kind', '') == KALENDER for e in eigene),
                'mitschriften': bool(zugang and MITSCHRIFT_SCOPE in zugang['scopes']),
                'besprechungen': besprechungen,
                'satz': None if zugang else GRUENDE['abgemeldet'],
            })
        return {'konten': ergebnis, **anmeldung.stand()}

    @app.post('/api/v1/microsoft/mitschriften/abholen', dependencies=guard)
    def abholen() -> dict[str, Any]:
        return {'ergebnis': mitschriften_holen(app), **konten()}

    takt_starten(app)


__all__ = ['AUTH', 'KALENDER', 'ablage', 'adressen', 'install_routes', 'ist_microsoft', 'kalender_leser',
           'mitschriften_holen', 'nach_entfernen', 'post_leser', 'takt_starten', 'zugang_da']
