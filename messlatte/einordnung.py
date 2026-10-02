"""Einordnung: die Stufe zwischen Aufnahme und Suche.

Im Produkt sucht `WorkingMemoryStore.search` nur in Quellen, die das lokale
Modell **eingeordnet** hat (`working_memory_worker.run`). Erst dadurch entsteht
der Suchindex. Die Wortsuche hängt nicht von der Art ab, die das Modell einem
Absatz zuweist: Der Index enthält Titel, Teilnehmer und Absatztext, unabhängig
von der Art.

Für die Messung ohne Modell (und für das Rauschen, das sonst zehntausende
Modellaufrufe kostete) gibt es deshalb `KonstanteEinordnung`: ein lokaler
„Anbieter“, der jedem Absatz die Art `fact` zuweist. Er läuft durch die echte
`interpret`-Funktion und den echten `WorkingMemoryStore.commit`. **Grenze:** Die
Qualität der Modelleinordnung (Bitte, Zusage, Absage …) wird so nicht gemessen;
gemessen wird nur, ob Aufnahme, Index und Suche die Quelle wiederfinden.
"""
from __future__ import annotations

import json

from icarus_memory.providers import ProviderError, Reply


class KonstanteEinordnung:
    """Weist jedem Absatz die Art `fact` zu. Kein Netzwerk, kein Modell."""

    name = 'messlatte'
    model = 'konstante-einordnung'
    is_local = True
    supports_json = True

    def complete_json(self, messages, *, max_tokens: int = 256, schema=None) -> Reply:
        try:
            blocks = json.loads(messages[-1]['content'])['blocks']
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError('Unerwartete Einordnungsanfrage') from exc
        return Reply(text=json.dumps({'items': [{'block_id': b['block_id'], 'kind': 'fact'} for b in blocks]}),
                     model=self.model)

    def complete(self, messages, tools) -> Reply:
        raise ProviderError('Die konstante Einordnung kennt nur complete_json.')


def einordnen(instanz, provider, quell_ids: list[str], *, paket: int = 200) -> dict:
    """Ordnet die genannten Episoden mit `provider` ein, über den Arbeitsgang des Produkts.

    `working_memory_worker.run` ist derselbe Weg wie im Betrieb (Freigabeprüfung
    mit der Gesprächssperre, `interpret`, `commit`). Wiederholt, bis nichts mehr
    ansteht; Zurückgestelltes (über der Obergrenze, gekürzt) und Fehlgeschlagenes (mit
    Wartezeit) hält das Produkt selbst zurück, die Schleife endet dann von allein.
    """
    from icarus_memory.working_memory_store import WorkingMemoryStore
    from icarus_memory.working_memory_worker import Zwischenstand, run

    if not quell_ids:
        return {'pakete': 0}
    store = WorkingMemoryStore(instanz.episodes)
    lock = instanz.app.state.conversation_lock
    zwischenstand = Zwischenstand()
    pakete = 0
    while store.pending(limit=1, episode_ids=quell_ids):
        for start in range(0, len(quell_ids), paket):
            run(instanz.episodes, provider, lock, limit=paket, source_ids=quell_ids[start:start + paket],
                stand=zwischenstand)
        pakete += 1
        # Lange Quellen gehen in Häppchen durch (Abschnitte je Paket begrenzt): dafür braucht es mehr Durchgänge.
        if pakete > 20_000:  # Sicherung gegen eine Schleife, die nichts mehr bewegt
            break
    return {'pakete': pakete}


def stand(instanz) -> dict:
    """Zähler des Produkts: total, done, skipped, retry, remaining."""
    from icarus_memory.working_memory_store import WorkingMemoryStore
    return WorkingMemoryStore(instanz.episodes).progress()
