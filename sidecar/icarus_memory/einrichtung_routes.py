"""Verdrahtung des Erststart-Assistenten und der sichtbaren Hintergrundarbeit.

Der Assistent selbst ist Oberfläche (`app/kingfisher/src/Einrichtung/`). Er baut keine zweite Anbindung an
Mail, Kalender oder Modelle, sondern nutzt die vorhandenen Routen. Hier steht nur, was der Server dazu weiß:

* `GET /api/v1/einrichtung`: Name für den Gruß, je Schritt „erledigt“ oder „übersprungen“, ob der Assistent
  schon abgeschlossen wurde, was von dem Wesentlichen (Mail, Kalender, Modell) schon da ist, und ob der
  Assistent jetzt von selbst erscheinen soll (`zeigen`), und ob dieser Rechner den Autostart einrichten kann
  (`autostart_verfuegbar`; sonst blendet der Assistent den Schritt „Beim Anmelden“ aus, Fremdprobe Befund 26).
* `PUT /api/v1/einrichtung`: Name, einen Schritt als erledigt/übersprungen/offen vermerken, den Assistenten
  abschließen oder neu beginnen lassen. Nichts davon löst etwas Außenwirksames aus: Es ist nur der Merkzettel.
* `GET /api/v1/einrichtung/lernt`: was im Hintergrund gerade läuft und der Oberfläche noch nicht gemeldet wird
  (die Berechnung der Akten). Die Mailaufnahme meldet `GET /api/v1/mail/intake`. Der Aufruf stößt die
  Berechnung der Akten an, wenn sie offen ist, wie es jede Ansicht der Akten tut.

Der Stand steht in den Einstellungen (`Settings.einrichtung`) und nicht nur im Browser: Nach einem Neustart oder
in einem anderen Fenster geht es dort weiter, wo man aufgehört hat.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import config

#: Die Schritte in ihrer Reihenfolge. Die Oberfläche kennt dieselben Kennungen (`Einrichtung/schritte.ts`).
SCHRITTE = ('name', 'mail', 'kalender', 'modell', 'freigaben', 'autostart', 'fertig')
STAENDE = ('erledigt', 'uebersprungen', 'offen')


class SchrittIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Literal['name', 'mail', 'kalender', 'modell', 'freigaben', 'autostart', 'fertig']
    stand: Literal['erledigt', 'uebersprungen', 'offen']


class EinrichtungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, max_length=80)
    schritt: SchrittIn | None = None
    abgeschlossen: bool | None = None
    neu_beginnen: bool | None = None


def _sauber(rohes: Any) -> dict[str, Any]:
    """Der gespeicherte Stand in fester Form; Unbekanntes (etwa aus einer neueren Version) fällt weg."""
    rohes = rohes if isinstance(rohes, dict) else {}
    schritte = rohes.get('schritte') if isinstance(rohes.get('schritte'), dict) else {}
    return {'name': str(rohes.get('name') or '').strip()[:80],
            'schritte': {k: v for k, v in schritte.items() if k in SCHRITTE and v in STAENDE and v != 'offen'},
            'abgeschlossen': rohes.get('abgeschlossen') is True}


def _zeitzone() -> str:
    """Der Name der Zeitzone, in der Kingfisher Uhrzeiten liest („Europe/Berlin“). Nur zum Anzeigen in den Einstellungen:
    Gewählt wird sie nicht (Vorgabe Europe/Berlin, sonst `KINGFISHER_TIMEZONE`)."""
    from .model import user_timezone
    zone = user_timezone()
    return str(getattr(zone, 'key', '') or 'UTC')


def register(app, guard, data_dir) -> None:
    def vorhanden() -> dict[str, bool]:
        """Was vom Wesentlichen schon da ist. Ein Zugang ohne Passwort zählt nicht: Damit lässt sich nichts abrufen."""
        from .server import _integration_secret
        settings = app.state.settings
        mail = any(e.configured and e.enabled and (_integration_secret(app, 'mail', e.id) or e.auth_method != 'password')
                   for e in settings.mail_accounts)
        mac = getattr(app.state, 'mac_calendar', None)
        try:
            stand = mac.public() if mac is not None else {}
        except Exception:  # noqa: BLE001 - ein ausgefallener Adapter darf die Einrichtung nicht blockieren
            stand = {}
        kalender = any(e.configured and e.enabled for e in settings.calendar_sources) \
            or bool(stand.get('enabled') and stand.get('selected'))
        modell = bool(settings.model) or getattr(app.state.agent, 'provider', None) is not None
        return {'mail': mail, 'kalender': kalender, 'modell': modell}

    def stand() -> dict[str, Any]:
        eigener = _sauber(app.state.settings.einrichtung)
        da = vorhanden()
        # Von selbst erscheint der Assistent nur, solange er nicht abgeschlossen ist und Wesentliches fehlt.
        return {**eigener, 'vorhanden': da, 'zeigen': not eigener['abgeschlossen'] and not all(da.values()),
                'zeitzone': _zeitzone(), 'autostart_verfuegbar': autostart_verfuegbar()}

    def autostart_verfuegbar() -> bool:
        """Ein Helfer auf dem Rechner hat sich gemeldet (Mac). Im Browser oder unter Docker gibt es keinen."""
        lesen = getattr(app.state, 'autostart_stand', None)
        try:
            return bool(lesen()['verfuegbar']) if lesen is not None else False
        except Exception:  # noqa: BLE001 - ohne Auskunft gilt: nicht verfügbar
            return False

    @app.get('/api/v1/einrichtung', dependencies=guard)
    def einrichtung() -> dict[str, Any]:
        return stand()

    @app.put('/api/v1/einrichtung', dependencies=guard)
    def einrichtung_setzen(body: EinrichtungIn) -> dict[str, Any]:
        with app.state.conversation_lock:
            neu = _sauber(app.state.settings.einrichtung)
            if body.neu_beginnen:
                neu.update(schritte={}, abgeschlossen=False)
            if body.name is not None:
                neu['name'] = body.name.strip()
            if body.schritt is not None:
                if body.schritt.stand == 'offen':
                    neu['schritte'].pop(body.schritt.id, None)
                else:
                    neu['schritte'][body.schritt.id] = body.schritt.stand
            if body.abgeschlossen is not None:
                neu['abgeschlossen'] = body.abgeschlossen
            vorher = app.state.settings.einrichtung
            app.state.settings.einrichtung = neu
            try:
                config.save(data_dir(), app.state.settings)
            except Exception:
                app.state.settings.einrichtung = vorher
                raise HTTPException(500, 'Der Stand der Einrichtung konnte nicht gespeichert werden.') from None
        return stand()

    @app.get('/api/v1/einrichtung/lernt', dependencies=guard)
    def lernt() -> dict[str, Any]:
        from .akten_routes import bausteine, nachfuehren
        bezuege, _ = bausteine(app)
        try:
            gesamt = bezuege.stand()['quellen']
            offen = nachfuehren(app)['offen']
        except Exception:  # noqa: BLE001 - Die Anzeige ist Beiwerk; sie darf nie eine Seite kippen
            return {'akten': None}
        return {'akten': {'offen': int(offen), 'gesamt': int(gesamt)} if offen else None}
