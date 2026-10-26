"""Wege nach draußen, die der Mensch sehen und abschalten kann (Paket D der Persona-Prüfung, 26.10.2026).

Drei Dinge an einer Stelle:

* **Wohin eine Cloud-Anfrage geht** (`ANBIETER`): je Anbieter ein Name mit Land und ein Halbsatz zur Region der
  Verarbeitung. Die Einwilligung nennt beides (`model_roles_routes.anbieter_liste`), statt „den Cloudanbieter, den
  du gewählt hast“ zu sagen, auch wenn niemand gewählt hat. Die Angaben folgen den datierten Fakten in
  `cloud_provider_facts.py`; sie sind keine rechtliche Zusicherung.
* **Was wann an welchen Anbieter ging** (`vermerken`, `GET /api/v1/cloud/protokoll`): jede einzelne Anfrage an
  einen Cloudanbieter steht im Logbuch (Art `cloud_anfrage`), ohne Inhalt: Zeit, Anbieter, Modell, wofür. Geschrieben
  wird unmittelbar vor dem Versand, nachdem die Einwilligung noch einmal geprüft wurde (Gespräch, Gedächtnis, Fragen
  verstehen in `agent.py`; Einordnung und Aufbau aus der Cloud in `source_processing_policy.ScopedProvider`).
* **Der Webabruf als Schalter** (`GET/PUT /api/v1/darf/web`): Ist er aus, bekommt das Modell das Werkzeug
  `web_abruf` gar nicht erst angeboten. Ist er an (Vorgabe), braucht jeder einzelne Abruf trotzdem die Freigabe im
  Gespräch (`policy.Policy._IMMER_FREIGABE`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict

from . import logbuch

#: Anbieter → (Name mit Land, wo verarbeitet wird). Kurz genug für einen Satz der Einwilligung.
ANBIETER: dict[str, tuple[str, str]] = {
    'anthropic': ('Anthropic (USA)', 'nicht nur in der EU verarbeitet'),
    'openai': ('OpenAI (USA)', 'nicht nur in der EU verarbeitet'),
    'chatgpt': ('OpenAI (USA)', 'nicht nur in der EU verarbeitet'),
    'mistral': ('Mistral (Frankreich)', 'in der EU oder der EFTA verarbeitet'),
    'openrouter': ('OpenRouter (USA)', 'in der Europa-Region verarbeitet (EU, EWR, Großbritannien oder Schweiz)'),
    'ollama-cloud': ('Ollama (USA)', 'nicht nur in der EU verarbeitet'),
}

#: Wofür eine Anfrage hinausging, und was dabei mitging. Kein Inhalt, nur die Art.
WOFUER: dict[str, tuple[str, str]] = {
    'gespraech': ('Antwort im Gespräch', 'deine Frage, der Gesprächsverlauf und was Kingfisher dazu gelesen hat'),
    'gedaechtnis': ('Frage an dein Gedächtnis', 'deine Frage und Inhalte der dazu gefundenen Quellen'),
    'frage': ('Frage verstehen', 'deine Frage'),
    'einordnung': ('Mail einordnen', 'eine neue Mail mit Inhalt, Absender und Betreff'),
    'import': ('Gedächtnis aus der Cloud aufbauen', 'Inhalt einer Quelle'),
}

MAX_EINTRAEGE = 30
RUECKBLICK = timedelta(days=30)


def wohin(anbieter_id: str) -> str:
    return ANBIETER.get(anbieter_id, (anbieter_id or 'ein Cloudanbieter', ''))[0]


def region(anbieter_id: str) -> str:
    return ANBIETER.get(anbieter_id, ('', 'nicht nur in der EU verarbeitet'))[1]


def anbieter_id(anbieter: Any) -> str:
    """Die Kennung des Anbieters: aus der Marke der Einwilligung (`model_roles._markiert`), sonst sein Name."""
    marke = getattr(anbieter, 'cloud_einwilligung', None)
    if isinstance(marke, tuple) and len(marke) == 3 and isinstance(marke[1], str) and marke[1]:
        return marke[1]
    if getattr(anbieter, 'ueber_ollama_cloud', False):
        return 'ollama-cloud'
    return str(getattr(anbieter, 'name', '') or 'cloud')


def vermerken(anbieter: Any, wofuer: str) -> None:
    """Hält eine einzelne Anfrage an einen Cloudanbieter fest, ohne Inhalt. Wirft nie (`logbuch.vermerke`)."""
    logbuch.vermerke('cloud_anfrage', anbieter=anbieter_id(anbieter), modell=str(getattr(anbieter, 'model', '') or ''),
                     wofuer=wofuer if wofuer in WOFUER else 'gespraech')


def satz(daten: dict[str, Any]) -> str:
    """„Mail einordnen · Anthropic (USA): eine neue Mail mit Inhalt, Absender und Betreff“."""
    titel, was = WOFUER.get(str(daten.get('wofuer') or ''), WOFUER['gespraech'])
    return f'{titel} · {wohin(str(daten.get("anbieter") or ""))}: {was}'


def protokoll(buch: logbuch.Logbuch | None, jetzt: datetime | None = None) -> list[dict[str, Any]]:
    """Die letzten Cloud-Anfragen, neueste zuerst (höchstens `MAX_EINTRAEGE`, höchstens `RUECKBLICK` zurück)."""
    if buch is None:
        return []
    jetzt = jetzt or datetime.now(timezone.utc)
    eintraege = [e for e in buch.ereignisse(jetzt - RUECKBLICK) if e.art == 'cloud_anfrage']
    return [{'zeit': e.zeit.isoformat(timespec='seconds'), 'anbieter': wohin(str(e.daten.get('anbieter') or '')),
             'modell': str(e.daten.get('modell') or ''), 'wofuer': str(e.daten.get('wofuer') or ''),
             'satz': satz(e.daten)} for e in reversed(eintraege[-MAX_EINTRAEGE:])]


def web_an(settings: Any) -> bool:
    return getattr(settings, 'web_abruf', 'an') != 'aus'


class WebIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    an: bool


def register(app, guard, data_dir: Callable[[], Any], rebuild: Callable[[], Any]) -> None:
    from . import config

    @app.get('/api/v1/cloud/protokoll', dependencies=guard)
    def cloud_protokoll() -> dict[str, Any]:
        """Was in den letzten 30 Tagen an welchen Cloudanbieter ging, ohne Inhalte. Verändert nichts."""
        return {'eintraege': protokoll(getattr(app.state, 'logbuch', None))}

    @app.get('/api/v1/darf/web', dependencies=guard)
    def web_lesen() -> dict[str, bool]:
        return {'an': web_an(app.state.settings)}

    @app.put('/api/v1/darf/web', dependencies=guard)
    def web_schalten(body: WebIn) -> dict[str, bool]:
        """Webabruf an oder aus. Aus wartet nie auf eine laufende Antwort; der Neubau nimmt dem Modell das Werkzeug."""
        settings = app.state.settings
        sperre = app.state.conversation_lock
        gesperrt = sperre.acquire(blocking=body.an)
        try:
            settings.web_abruf = 'an' if body.an else 'aus'
            config.save(data_dir(), settings)
        finally:
            if gesperrt:
                sperre.release()
        rebuild()
        return {'an': web_an(settings)}


__all__ = ['ANBIETER', 'WOFUER', 'anbieter_id', 'protokoll', 'region', 'register', 'satz', 'vermerken', 'web_an',
           'wohin']
