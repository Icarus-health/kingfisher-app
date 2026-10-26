"""Gedächtnisantworten über die Cloud, nur mit gültiger Einwilligung der Rolle `antwort`.

Entscheidung des Nutzers vom 26.10.2026 (`docs/66-automatik.md`, Paket T): Ist „Cloud für Fragen und
Antworten“ eingeschaltet, beantwortet der gewählte Cloudanbieter auch Fragen an das Gedächtnis, also die
Auswahl der Quellen (`working_memory_answers.prepare`) und die Sätze (`satzantwort.formulieren`). Der
Einwilligungssatz der Rolle sagt, was dabei hinausgeht: die Frage und die dafür gefundenen Textstellen.

Was hier gilt, ohne Ausnahme:

* **Eine Fähigkeit, kein Schalter im Anbieter.** Die Gedächtniswege nehmen einen Anbieter nur, wenn er lokal
  ist oder ein `GedaechtnisCloud` ist (`erlaubt`). Einen solchen baut nur der Agent, und nur, wenn die
  Verdrahtung (`freigabe_gueltig`) die Einwilligung **jetzt** bestätigt. Ein bloß nicht lokaler Anbieter
  (Standardanbieter aus der Umgebung, Cloud ohne Einwilligung, Rückfall bei fehlendem Schlüssel) bleibt
  draußen: Die Antwort sagt dann wie bisher, dass ein lokales Modell nötig ist.
* **Vor jedem Versand erneut geprüft.** `complete_json` fragt vor jedem Aufruf, ob die Einwilligung noch gilt,
  und lässt die Nutzlast durch die Ausgangsprüfung des Agenten laufen (`Agent.assert_egress_allowed`, Grenze
  `normal`). Fällt eins davon, geht nichts hinaus (`ProviderError`), und die Antwort fällt auf „konnte nicht
  zuverlässig ausgewählt werden“ beziehungsweise auf die wörtlichen Belege zurück.
* **Gleiche Belegbindung.** Der Cloudanbieter liefert nur JSON nach demselben Schema wie das lokale Modell; die
  Prüfung der Referenzen, der Sätze und das zweite Tor (Rolle `pruefung`, immer lokal oder aus) bleiben gleich.
* **Bestätigtes Wissen bleibt im Haus.** Die Wissensschicht hat keine feinere Schutzbedarfsmarkierung und geht
  nie an einen fremden Anbieter (`Agent._knowledge_context_items`). Bestätigte Einträge zur Frage stehen in der
  Antwort weiter darunter, lokal gelesen, aber sie gehen nicht in die Nutzlast.
* **Einbettung, Prüfung, Hintergrund bleiben lokal** (`model_roles.anbieter_nur_lokal`); hier ändert sich daran
  nichts.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable

from .providers import ProviderError, Reply

#: Was bei einer Gedächtnisantwort über die Cloud an den Anbieter geht (Metadaten der Antwort, ehrlich benannt).
GESENDET = ('frage', 'textstellen')


class GedaechtnisCloud:
    """Der Cloudanbieter der Rolle `antwort`, eingegrenzt auf Gedächtnisantworten unter gültiger Einwilligung.

    `pruefen(messages)` wirft, wenn die Einwilligung nicht mehr gilt oder die Nutzlast die Ausgangsprüfung nicht
    besteht. Der innere Anbieter braucht nur `complete` (Anthropic, OpenAI-kompatibel, Ollama-Cloud): Die
    JSON-Form erzwingt hier die Anweisung, die Prüfung danach der Aufrufer.
    """

    is_local = False
    is_remote = True

    def __init__(self, anbieter: Any, pruefen: Callable[[list[dict[str, Any]]], None]) -> None:
        self._anbieter = anbieter
        self._pruefen = pruefen
        self.name = str(getattr(anbieter, 'name', '') or 'cloud')
        self.model = str(getattr(anbieter, 'model', '') or '')
        self.aufrufe = 0

    @property
    def innerer(self) -> Any:
        return self._anbieter

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        """Freie Antworten gibt es auf diesem Weg nicht: Das Gedächtnis nimmt nur geprüftes JSON."""
        raise ProviderError('Gedächtnisantworten über die Cloud nehmen nur JSON nach Schema.')

    def complete_json(self, messages: list[dict[str, Any]], *, max_tokens: int = 256,
                      schema: dict[str, Any] | None = None) -> Reply:
        try:
            self._pruefen(messages)
        except ProviderError:
            raise
        except Exception as fehler:  # noqa: BLE001 - jede verweigerte Prüfung heißt: nichts geht hinaus
            raise ProviderError('Die Cloud ist für diese Antwort nicht freigegeben.') from fehler
        nachrichten = _mit_form(messages, schema)
        self.aufrufe += 1
        antwort = self._anbieter.complete(nachrichten, [])
        if getattr(antwort, 'tool_calls', None):
            raise ProviderError('Der Cloudanbieter wollte ein Werkzeug benutzen.')
        return Reply(text=json_aus(getattr(antwort, 'text', None)), model=self.model)

    def metadaten(self) -> dict[str, Any]:
        """Für `context['gedaechtnis_cloud']`: wohin die Frage und die Textstellen gingen."""
        return {'anbieter': self.name, 'modell': self.model, 'gesendet': list(GESENDET)}


_FORM = ('\n\nAntworte ausschließlich mit einem einzigen JSON-Objekt nach diesem JSON-Schema, ohne Text davor oder '
         'danach und ohne Codeblock:\n')


def _mit_form(messages: list[dict[str, Any]], schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Die Nachrichten mit der Pflicht zur JSON-Form in der Systemanweisung (Cloudanbieter kennen kein Schema-Feld)."""
    form = _FORM + json.dumps(schema or {'type': 'object'}, ensure_ascii=False)
    kopie = [dict(m) for m in messages]
    for nachricht in kopie:
        if nachricht.get('role') == 'system' and isinstance(nachricht.get('content'), str):
            nachricht['content'] += form
            return kopie
    return [{'role': 'system', 'content': form.strip()}, *kopie]


_ZAUN = re.compile(r'^```(?:json)?\s*(.*?)\s*```$', re.S)


def json_aus(text: Any) -> str:
    """Genau ein JSON-Objekt aus der Antwort, sonst `ProviderError`. Ein Codeblock darum wird abgelegt."""
    if not isinstance(text, str) or len(text) > 16000:
        raise ProviderError('Der Cloudanbieter lieferte keine lesbare Auswahl.')
    roh = text.strip()
    zaun = _ZAUN.match(roh)
    if zaun:
        roh = zaun.group(1).strip()
    try:
        wert = json.loads(roh)
    except ValueError as fehler:
        raise ProviderError('Der Cloudanbieter lieferte kein JSON.') from fehler
    if not isinstance(wert, dict):
        raise ProviderError('Der Cloudanbieter lieferte kein JSON-Objekt.')
    return json.dumps(wert, ensure_ascii=False)


def erlaubt(anbieter: Any) -> bool:
    """Darf dieser Anbieter Quellentext für eine Gedächtnisantwort sehen? Lokal, oder ein `GedaechtnisCloud`."""
    if anbieter is None:
        return False
    return getattr(anbieter, 'is_local', False) is True or isinstance(anbieter, GedaechtnisCloud)


def ist_cloud(anbieter: Any) -> bool:
    return isinstance(anbieter, GedaechtnisCloud)


def markierung(rolle: str, anbieter: str, einwilligung: str) -> tuple[str, str, str]:
    """Was `model_roles` an einen Cloudanbieter heftet, den es mit gültiger Einwilligung gebaut hat."""
    return (rolle, anbieter, einwilligung)


def freigabe_gueltig(app: Any, anbieter: Any) -> bool:
    """Gilt die Einwilligung der Rolle `antwort` jetzt, und ist `anbieter` genau der damit gebaute Cloudanbieter?

    Liest die gespeicherte Wahl bei jedem Aufruf neu. Nein, wenn der Schalter aus ist, die Einwilligung fehlt oder
    nicht lesbar ist, der Anbieter lokal ist, oder er zu einer anderen (älteren) Einwilligung gehört.
    """
    from .model_roles import einwilligung_gueltig, lese_wahlen

    if anbieter is None or getattr(anbieter, 'is_local', False):
        return False
    wahl = lese_wahlen(getattr(getattr(app.state, 'settings', None), 'model_roles', None)).get('antwort')
    if wahl is None or wahl.local_only or not einwilligung_gueltig('antwort', wahl):
        return False
    try:
        datetime.fromisoformat(wahl.cloud_einwilligung)
    except (TypeError, ValueError):
        return False
    return getattr(anbieter, 'cloud_einwilligung', None) == markierung('antwort', wahl.anbieter,
                                                                       wahl.cloud_einwilligung)


__all__ = ['GESENDET', 'GedaechtnisCloud', 'erlaubt', 'freigabe_gueltig', 'ist_cloud', 'json_aus', 'markierung']
