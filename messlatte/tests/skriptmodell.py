"""Ein skriptbares „Modell“ für die Tests der Antwortstufe.

Es ist ein lokaler Anbieter im Sinne des Produkts (`is_local`, `complete_json`,
`complete`) und antwortet nach Regeln statt nach Sprache:

* Einordnungsanfragen (`working_memory_analysis.interpret`): jeder Absatz `fact`.
* Auswahlanfragen (`working_memory_answers.prepare`): wählt die Quellen, in deren
  Text ein Stichwort der passenden Regel steht; ohne Regel keine (`no_relevant_sources`).
* Sätze (E3, `satzantwort.py`): je Regel eine Antwort `{saetze, status}` oder ein Rückruf auf die Anfrage; ohne
  Regel „unklar“ (dann gelten die Zitate).
* Prüfmodus (Rolle `pruefung`, zweites Tor, `satzpruefung_modell.py`): je Regel (Text im geprüften Satz) ein Urteil
  `ja`, `nein`, `unklar`, eine Ausnahme oder ein Rückruf auf den Satz; ohne Regel `ja`. Jede Anfrage wird gemerkt.
* Freier Chat (`complete`): eine feste Antwort.

So lässt sich die Antwortstufe von der Aufnahme bis zur Bewertung prüfen, ohne
ein echtes Modell, und jede Regel ist im Test sichtbar.
"""
from __future__ import annotations

import json

from icarus_memory import satzpruefung_modell
from icarus_memory.providers import Reply


class SkriptModell:
    name = 'skript'
    model = 'skript-1'
    is_local = True
    supports_json = True

    def __init__(self, regeln: dict[str, list[str]] | None = None, chat: str = 'Das weiß ich nicht.',
                 saetze: dict | None = None, pruefung: dict | None = None):
        # Schlüssel: Text in der Frage; Wert: Antwort der Satzanfrage (dict) oder Rückruf(anfrage) -> dict
        self.saetze = saetze or {}
        # Prüfmodus: Schlüssel Text im geprüften Satz; Wert „ja“/„nein“/„unklar“, Ausnahme oder Rückruf(satz) -> Urteil
        self.pruefung = pruefung or {}
        self.pruefanfragen: list[str] = []
        self.satzanfragen: list[dict] = []
        # Schlüssel: Text, der in der Frage vorkommen muss; Wert: Stichwörter der zu wählenden Quellen
        self.regeln = regeln or {}
        self.chat = chat
        self.auswahlen: list[dict] = []
        self.einordnungen = 0
        self.chats = 0

    def _pruefen(self, messages):
        satz = satzpruefung_modell.satz_der_anfrage(messages) or ''
        self.pruefanfragen.append(satz)
        regel = next((r for k, r in self.pruefung.items() if k.casefold() in satz.casefold()), 'ja')
        urteil = regel(satz) if callable(regel) else regel
        if isinstance(urteil, Exception):
            raise urteil
        return Reply(text=json.dumps({'urteil': urteil}), model=self.model)

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        if satzpruefung_modell.ist_pruefanfrage(messages):
            return self._pruefen(messages)
        system = messages[0]['content']
        nutzer = json.loads(messages[-1]['content'])
        if system.startswith('Du formulierst die Antwort auf eine Frage'):
            self.satzanfragen.append(nutzer)
            regel = next((r for k, r in self.saetze.items() if k.casefold() in nutzer['anliegen'].casefold()), None)
            antwort = regel(nutzer) if callable(regel) else regel or {'status': 'unklar', 'saetze': []}
            return Reply(text=json.dumps(antwort), model=self.model)
        if system.startswith('Ordne jeden nummerierten ORIGINALBLOCK'):
            self.einordnungen += 1
            items = [{'block_id': b['block_id'], 'kind': 'fact'} for b in nutzer['blocks']]
            return Reply(text=json.dumps({'items': items}), model=self.model)
        frage = nutzer['question'].casefold()
        woerter = next((w for schluessel, w in self.regeln.items() if schluessel.casefold() in frage), None)
        ids = [q['id'] for q in nutzer['sources'] if str(q['id']).startswith('S') and woerter
               and any(w.casefold() in q.get('context', '').casefold() for w in woerter)]
        self.auswahlen.append({'frage': nutzer['question'], 'ids': ids})
        status = 'source_reports' if ids else 'no_relevant_sources'
        return Reply(text=json.dumps({'status': status, 'ids': ids}), model=self.model)

    def complete(self, messages, tools):
        self.chats += 1
        return Reply(text=self.chat, model=self.model)
