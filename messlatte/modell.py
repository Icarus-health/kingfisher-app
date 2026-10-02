"""Modellwahl der Messlatte: `--modell` in einen Anbieter des Produkts übersetzen.

    keins                              kein Modell; die Stufe „Antwort“ entfällt
    ollama:NAME                        lokaler Ollama (http://localhost:11434/v1)
    kompatibel:URL:NAME                jeder Server mit /chat/completions; die URL braucht
                                       einen Pfad (http://127.0.0.1:1234/v1:qwen2.5:14b)
    anthropic:NAME                     Cloud; nur mit ANTHROPIC_API_KEY in der Umgebung
    skript:ART                         Skriptmodell nach den Skripten der Welt (`skript.py`): sorgfaeltig,
                                       unaufmerksam, pruefung (für --modell-pruefung); misst die Mechanik

Gebaut wird mit den Klassen aus `providers.py`, mit denselben Parametern wie
`providers.from_env`. Die Messlatte ändert keine Produktvorgabe: Ob ein Anbieter
als lokal gilt, entscheidet allein das Produkt (`is_local_endpoint`). Ein Cloud-
Anbieter durchläuft deshalb den Weg, den das Produkt für ihn vorsieht; seine
Antworten auf Gedächtnisfragen sind dann meist „nur lokal“ und werden als
verweigert gewertet.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping


class ModellFehler(ValueError):
    pass


@dataclass(frozen=True)
class ModellWahl:
    art: str  # keins | ollama | kompatibel | anthropic | skript
    name: str = ''
    url: str = ''
    schluessel: str = ''

    @property
    def bezeichnung(self) -> str:
        """Was im Bericht steht; nie ein Schlüssel."""
        return {'keins': 'keins', 'ollama': f'ollama:{self.name}', 'kompatibel': f'kompatibel:{self.url}:{self.name}',
                'anthropic': f'anthropic:{self.name}', 'skript': f'skript:{self.name}'}[self.art]


def lese_modell(text: str, umgebung: Mapping[str, str] | None = None) -> ModellWahl:
    """Zerlegt `--modell`. Wirft `ModellFehler` mit einer Meldung, die sagt, was fehlt."""
    umgebung = os.environ if umgebung is None else umgebung
    text = (text or 'keins').strip()
    if text == 'keins':
        return ModellWahl('keins')
    art, _, rest = text.partition(':')
    if art == 'ollama' and rest:
        return ModellWahl('ollama', name=rest)
    if art == 'kompatibel':
        treffer = re.fullmatch(r'(https?://[^/\s]+/[^\s:]*):(\S+)', rest)
        if not treffer:
            raise ModellFehler('„kompatibel“ braucht kompatibel:URL:NAME mit Pfad in der URL, '
                               'etwa kompatibel:http://127.0.0.1:1234/v1:qwen2.5:14b')
        schluessel = umgebung.get('OPENAI_API_KEY') or umgebung.get('LLM_API_KEY') or ''
        return ModellWahl('kompatibel', name=treffer.group(2), url=treffer.group(1), schluessel=schluessel)
    if art == 'anthropic' and rest:
        schluessel = umgebung.get('ANTHROPIC_API_KEY', '')
        if not schluessel:
            raise ModellFehler('Für anthropic:NAME muss ANTHROPIC_API_KEY in der Umgebung stehen.')
        return ModellWahl('anthropic', name=rest, schluessel=schluessel)
    if art == 'skript':
        from .skript import ARTEN
        if rest not in ARTEN:
            raise ModellFehler(f'„skript“ braucht eine Art: {", ".join(ARTEN)} (etwa skript:sorgfaeltig).')
        return ModellWahl('skript', name=rest)
    raise ModellFehler(f'Unbekanntes Modell „{text}“. Erlaubt: keins, ollama:NAME, kompatibel:URL:NAME, anthropic:NAME, '
                       'skript:ART.')


def baue_anbieter(wahl: ModellWahl, fragen=()):
    """Der Anbieter des Produkts zur Wahl; None bei „keins“. `fragen` braucht nur das Skriptmodell (seine Sätze)."""
    if wahl.art == 'keins':
        return None
    if wahl.art == 'skript':
        from .skript import WeltSkript
        return WeltSkript(wahl.name, fragen)
    from icarus_memory.providers import Anthropic, OpenAICompatible

    if wahl.art == 'anthropic':
        return Anthropic(wahl.name, wahl.schluessel)
    if wahl.art == 'ollama':
        anbieter = OpenAICompatible(wahl.name, api_key='ollama', base_url='http://localhost:11434/v1')
    else:
        anbieter = OpenAICompatible(wahl.name, api_key=wahl.schluessel or 'kein-schluessel', base_url=wahl.url)
    if anbieter.is_local:
        # Wie `scripts/probe_cos_workweek.py`: lokale Aufrufe nehmen keinen Umgebungs-Proxy.
        anbieter._verified_local_transport = True
    return anbieter
