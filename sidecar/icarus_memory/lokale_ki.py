"""Eine Aussage zur lokalen KI, aus einer Quelle (Fremdprobe, Befund 9).

Nach „Alles eingerichtet und geprüft“ sagten die Einstellungen gleichzeitig „Anderer Anbieter eingerichtet“, „Keine
Modellliste erreichbar“ und „Ollama meldet noch kein installiertes Modell“. Die drei Stellen fragten drei Dinge: den
Namen des Anbieters in der Einstellungsdatei (nach „Alles einrichten“ leer), eine fest eingetragene Adresse
(`host.docker.internal`, außerhalb von Docker nicht erreichbar) und dieselbe Adresse noch einmal.

Hier steht der eine Stand: das Modell, das tatsächlich antwortet (Anbieter des Agenten), die Adresse, unter der
Kingfisher Ollama selbst findet (`lokaler_endpunkt`), und das Inventar von Ollama (`ollama_inventar`, 30 s gemerkt).
Daraus ein Zustand und ein Satz. Die Oberfläche zeigt nur diesen Satz, nirgends einen eigenen.
"""
from __future__ import annotations

from typing import Any

from .model_recommendation import normalisiere
from .model_roles import lokaler_endpunkt, ollama_wurzel, rollen_von
from .ollama_inventar import CLOUD, LOKAL, inventar_von

#: Die Zustände, in der Reihenfolge, in der sie geprüft werden.
ZUSTAENDE = ('keins', 'cloud', 'nicht_erreichbar', 'fehlt', 'bereit')


def stand(app: Any) -> dict[str, Any]:
    """Zustand, Kurzform für Karten, ein Satz, und was Ollama an Modellen hat (lokal und über Ollamas Cloud)."""
    provider = getattr(getattr(app.state, 'agent', None), 'provider', None)
    modell = str(getattr(provider, 'model', '') or '').strip() or None
    lokal = bool(getattr(provider, 'is_local', False))
    endpunkt = lokaler_endpunkt(rollen_von(app).standard())
    inventar = inventar_von(app).installiert(ollama_wurzel(endpunkt))
    installiert = sorted(n for n, art in (inventar or {}).items() if art == LOKAL)
    cloud = sorted(n for n, art in (inventar or {}).items() if art == CLOUD)
    basis = {'modell': modell, 'lokal': lokal, 'erreichbar': inventar is not None, 'endpunkt': endpunkt,
             'installiert': installiert, 'cloud': cloud}

    if provider is None or not modell:
        return {**basis, 'zustand': 'keins', 'kurz': 'Noch kein Modell eingerichtet',
                'satz': 'Noch kein Modell eingerichtet. Unter „Lokale KI“ richtet Kingfisher es mit einem Klick ein.'}
    if not lokal:
        return {**basis, 'zustand': 'cloud', 'kurz': f'Eingerichtet: {modell} (Cloud)',
                'satz': f'Eingerichtet: {modell}. Die Antworten kommen von einem Cloudanbieter, nicht von diesem Rechner.'}
    if inventar is None:
        return {**basis, 'zustand': 'nicht_erreichbar', 'kurz': f'{modell}: Ollama antwortet nicht',
                'satz': f'Eingerichtet ist {modell}, aber Ollama antwortet gerade nicht. '
                        'Starte Ollama; Kingfisher verbindet sich dann von selbst.'}
    if normalisiere(modell) not in {normalisiere(n) for n in installiert}:
        return {**basis, 'zustand': 'fehlt', 'kurz': f'{modell}: fehlt in Ollama',
                'satz': f'Eingerichtet ist {modell}, aber Ollama hat dieses Modell nicht. '
                        'Unter „Lokale KI“ lädt Kingfisher es mit einem Klick.'}
    return {**basis, 'zustand': 'bereit', 'kurz': f'Bereit: {modell}',
            'satz': f'Eingerichtet und bereit: {modell} läuft auf diesem Rechner.'}


__all__ = ['ZUSTAENDE', 'stand']
