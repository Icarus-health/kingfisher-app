"""Skriptmodelle der Messlatte: die Mechanik der Antwortstufe messen, ohne echtes Modell.

    --modell skript:sorgfaeltig        wählt die Quellen der Frage und schreibt den richtigen Satz
    --modell skript:unaufmerksam       schreibt den richtigen und dazu den falschen Satz
    --modell-pruefung skript:pruefung  Prüfmodell (Rolle `pruefung`): „nein“ für jeden falschen Satz der Welt, sonst „ja“

Die Sätze stehen in der Welt je Frage unter `skript` (FORMAT.md): `auswahl` (Wörter, an denen das Skript die Quellen
wählt und seine Belege erkennt), `richtig` und `falsch` (enthält eine verbotene Aussage der Frage). Fragen ohne
`skript` bekommen keine Auswahl und keine Sätze; sie laufen wie ohne Modell durch den Zitatmodus.
Im Original-ID-Modus wählt `sorgfaeltig` ausschließlich angebotene vollständige Einheiten.
`unaufmerksam` behält absichtlich freie Legacy-Fehlkandidaten für die Gatekontrollen.

**Was das misst und was nicht.** Gemessen wird, ob die Sätze durch beide Tore des Produkts gehen, was verworfen und
wie es gezählt wird, und ob ein durchgelassener falscher Satz in der Bewertung als falsche Aussage auftaucht. Das
Skript-Prüfmodell ist ein **ideales** Prüfmodell: Es kennt die falschen Sätze der Welt. Wie gut ein echtes
Prüfmodell urteilt, sagt erst Messlauf D (`docs/40-messplan-modelle.md`) mit `--modell-pruefung ollama:NAME`.
"""
from __future__ import annotations

import json
from collections.abc import Sequence

from icarus_memory import satzantwort, satzpruefung_modell
from icarus_memory.providers import Reply

from .bewertung import normalisiere
from .daten import Frage

ARTEN = ('sorgfaeltig', 'unaufmerksam', 'pruefung')


def _frage_zu(text: str, fragen: Sequence[Frage]) -> Frage | None:
    gesucht = normalisiere(text)
    return next((f for f in fragen if f.skript is not None and normalisiere(f.frage) == gesucht), None)


def _enthaelt(text: str, woerter: Sequence[str]) -> bool:
    text = normalisiere(text)
    return any(normalisiere(w) in text for w in woerter)


class WeltSkript:
    """Ein lokales „Modell“, das nach den Skripten der Welt antwortet (Auswahl und Sätze)."""

    name = 'skript'
    is_local = True
    supports_json = True

    def __init__(self, art: str, fragen: Sequence[Frage]):
        if art not in ARTEN:
            raise ValueError(art)
        self.art = art
        self.model = f'skript-{art}'
        self.fragen = tuple(fragen)
        self.pruefanfragen = 0

    # -- Rolle `pruefung` ------------------------------------------------------------------
    def _pruefen(self, messages) -> Reply:
        self.pruefanfragen += 1
        satz = normalisiere(satzpruefung_modell.satz_der_anfrage(messages) or '')
        falsch = any(f.skript is not None and normalisiere(f.skript.falsch) == satz for f in self.fragen)
        return Reply(text=json.dumps({'urteil': 'nein' if falsch else 'ja'}), model=self.model)

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        if satzpruefung_modell.ist_pruefanfrage(messages):
            return self._pruefen(messages)
        system = messages[0]['content']
        nutzer = json.loads(messages[-1]['content'])
        if satzantwort.ist_satzanfrage(messages):
            original = schema == satzantwort.ORIGINAL_SCHEMA or any('originalsaetze' in b for b in nutzer['belege'])
            feld = 'originalstellen' if original else 'saetze'
            frage = _frage_zu(nutzer['anliegen'], self.fragen)
            if frage is None or self.art == 'pruefung':
                return Reply(text=json.dumps({'status': 'unklar', feld: []}), model=self.model)
            gewaehlt = [b for b in nutzer['belege'] if _enthaelt(
                f"{b['quelle']} " + b.get('text', '\n'.join(s['text'] for s in b.get('originalsaetze', ()))),
                frage.skript.auswahl)]
            belege = [b['nr'] for b in gewaehlt]
            if not belege:
                return Reply(text=json.dumps({'status': 'nichts_vorliegend', feld: []}), model=self.model)
            if original and self.art == 'sorgfaeltig':
                stellen = [{'beleg': b['nr'], 'satz': s['nr']} for b in gewaehlt for s in b.get('originalsaetze', ())]
                return Reply(text=json.dumps({'status': 'antwort' if stellen else 'nichts_vorliegend',
                    'originalstellen': stellen[:satzantwort.MAX_SAETZE]}), model=self.model)
            # Absichtlich freie Legacy-Fehlkandidaten bleiben negative Gateproben.
            saetze = [{'text': frage.skript.richtig, 'belege': belege[:1]}]
            if self.art == 'unaufmerksam':
                saetze.append({'text': frage.skript.falsch, 'belege': belege[:1]})
            return Reply(text=json.dumps({'status': 'antwort', 'saetze': saetze}), model=self.model)
        if system.startswith('Ordne jeden nummerierten ORIGINALBLOCK'):
            items = [{'block_id': b['block_id'], 'kind': 'fact'} for b in nutzer['blocks']]
            return Reply(text=json.dumps({'items': items}), model=self.model)
        # Auswahl der Quellen: die Kandidaten, deren Kontext ein Wort der Auswahl trägt.
        frage = _frage_zu(nutzer.get('question', ''), self.fragen)
        ids = [q['id'] for q in nutzer.get('sources', ()) if str(q['id']).startswith('S') and frage is not None
               and _enthaelt(f"{q.get('title', '')} {q.get('context', '')} {q.get('text', '')}", frage.skript.auswahl)]
        return Reply(text=json.dumps({'status': 'source_reports' if ids else 'no_relevant_sources', 'ids': ids}),
                     model=self.model)

    def complete(self, messages, tools):
        if satzpruefung_modell.ist_pruefanfrage(messages):
            return self._pruefen(messages)
        return Reply(text='Das weiß ich nicht.', model=self.model)
