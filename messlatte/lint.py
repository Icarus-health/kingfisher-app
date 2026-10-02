"""Stufe „Lint“ (M2): Findet der Lint über alle Akten die Widerspruchsfälle der Welt, und nur sie?

Die Welt nennt je Szenario die Befunde, die der Lint finden soll (`lint` in FORMAT.md). Die Stufe
spielt die Welt ein wie die Stufe Akten (Regel-Einordnung statt Modell, `akten.RegelEinordnung`),
führt aus, was der Nutzer selbst getan hat (`handlungen.py`: Projekte, Zuordnungen, angenommene
Aussagen), stößt den Lint über die Route an (`POST /api/v1/lint`) und liest die offenen Befunde
(`GET /api/v1/lint/befunde`). Gezählt wird:

* **gefunden**: erwartete Befunde, zu denen ein Befund derselben Art (und Unterart) mit allen
  erwarteten Quellen als Beleg vorliegt;
* **Fehlalarme**: Befunde, die keine Erwartung trifft. Im Rauschen (alle Belege sind Rauschquellen)
  ist ein Hinweis „ruhend“ kein Fehlalarm, wenn er stimmt (jüngste Quelle älter als ein Jahr); jede
  andere Art im Rauschen ist ein Fehlalarm, denn das Rauschen widerspricht sich nicht.
* **Regel des Gedächtnisses**: Der Lauf darf keinen Fakt schreiben. Die Zahl der Aussagen im
  Wissensbestand und ihr Status müssen vorher und nachher gleich sein; Widersprüche erscheinen als
  offene Vorschläge.

**Grenze:** Ohne Modell entsteht keine Lage (Ebene 3); die Art `veralteter_satz` ist hier deshalb
nicht gemessen (die Tests prüfen sie mit einem Skriptmodell). Die Einordnung ist die Regel-Einordnung
der Stufe Akten; wer ihre Regeln ändert, ändert die Messung.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .aufnahme import ist_rauschen


@dataclass
class Treffer:
    art: str
    unterart: str
    quellen: tuple
    notiz: str = ''
    gefunden: bool = False
    text: str = ''


@dataclass
class LintMessung:
    erwartet: list = field(default_factory=list)
    fehlalarme: list = field(default_factory=list)
    """(Art, Unterart, Welt-IDs der Belege, Text) je Befund, den die Welt nicht erwartet."""
    rauschen_ruhend: int = 0
    befunde: int = 0
    vorschlaege_offen: int = 0
    aussagen_vorher: tuple = ()
    aussagen_nachher: tuple = ()
    lagen: int = 0
    dauer_s: float = 0.0
    sachen: int = 0

    @property
    def gefunden(self) -> int:
        return sum(1 for e in self.erwartet if e.gefunden)

    @property
    def fakten_unveraendert(self) -> bool:
        return self.aussagen_vorher == self.aussagen_nachher


def zuordnen(befunde: list[dict], erwartungen, episode_zu_welt: dict, stichtag: datetime) -> tuple[list, list, int]:
    """(Treffer je Erwartung, Fehlalarme, korrekte Hinweise „ruhend“ im Rauschen). Rein, ohne Produkt."""
    treffer = [Treffer(e.art, e.unterart, tuple(e.quellen), e.notiz) for e in erwartungen]
    fehlalarme, ruhend = [], 0
    for befund in befunde:
        welt_ids = {episode_zu_welt.get(b['episode_id'], '') for b in befund['belege']}
        passend = [t for t in treffer if t.art == befund['art'] and (not t.unterart or t.unterart == befund['unterart'])
                   and set(t.quellen) <= welt_ids]
        if passend:
            for t in passend:
                t.gefunden, t.text = True, befund['text']
            continue
        nur_rauschen = bool(welt_ids) and all(not w or ist_rauschen(w) for w in welt_ids)
        if nur_rauschen and befund['art'] == 'waise' and befund['unterart'] == 'ruhend' and all(
                datetime.fromisoformat(b['datum']) < stichtag - timedelta(days=365) for b in befund['belege']):
            ruhend += 1
            continue
        kennungen = sorted(episode_zu_welt.get(b['episode_id']) or b['episode_id'] for b in befund['belege'])
        fehlalarme.append((befund['art'], befund['unterart'], kennungen, befund['text']))
    return treffer, fehlalarme, ruhend


def _aussagen(instanz) -> tuple:
    return tuple(sorted((c.id, c.status.value) for c in instanz.claims.all_claims(include_inactive=True)))


def messen(instanz, welten, aufgenommen) -> LintMessung:
    """Bezüge wie im Betrieb (mit den Adressen des Nutzers), dann Lint über die Route und Abgleich mit der Welt."""
    from icarus_memory import akten_routes
    from icarus_memory.akten import Akten
    from icarus_memory.bezuege import Bezuege
    from icarus_memory.lage_routes import lagen_von

    app = instanz.app
    # Im Betrieb kennt das Produkt die eigenen Adressen aus den Konten; hier aus der Welt (wie die Stufe Akten).
    bezuege = Bezuege(instanz.episodes, workspace=app.state.workspace, eigene=lambda: list(instanz.eigene))
    akten = Akten(instanz.episodes, bezuege, claims=instanz.claims,
                  aufgaben=lambda sache, ids: akten_routes.aufgaben_zu(app, bezuege, sache, ids))
    app.state.akten_bausteine = (instanz.episodes, bezuege, akten)
    messung = LintMessung(aussagen_vorher=_aussagen(instanz), lagen=len(lagen_von(app).sachen()))
    begonnen = time.perf_counter()
    lauf = instanz.anfrage('POST', '/api/v1/lint')['lauf']
    messung.dauer_s = round(time.perf_counter() - begonnen, 2)
    messung.sachen = lauf.get('sachen', 0)
    befunde = instanz.anfrage('GET', '/api/v1/lint/befunde?status=offen')['befunde']
    messung.aussagen_nachher = _aussagen(instanz)
    messung.befunde = len(befunde)
    messung.vorschlaege_offen = sum(1 for b in befunde for v in b['vorschlaege'] if v['zustand'] == 'pending')
    episode_zu_welt = {episode: welt for welt, episode in aufgenommen.episoden.items()}
    erwartungen = [e for w in welten for e in w.lint_erwartungen]
    messung.erwartet, messung.fehlalarme, messung.rauschen_ruhend = zuordnen(
        befunde, erwartungen, episode_zu_welt, welten[0].stichtag)
    return messung


def markdown(m: LintMessung, *, rauschen: int = 0) -> str:
    ja = lambda wert: 'ja' if wert else '**nein**'  # noqa: E731
    zeilen = ['## Stufe Lint', '',
              f'Lint über alle Akten ({m.sachen} Sachen, {rauschen} Rauschquellen) in {m.dauer_s} s. '
              'Einordnung: `RegelEinordnung` (kein Modell).', '',
              f'**Erwartete Befunde gefunden: {m.gefunden} von {len(m.erwartet)}** · '
              f'**Fehlalarme: {len(m.fehlalarme)}** · Befunde insgesamt: {m.befunde}', '',
              f'- Regel des Gedächtnisses: Aussagen im Wissensbestand vorher {len(m.aussagen_vorher)}, nachher '
              f'{len(m.aussagen_nachher)}, unverändert: {ja(m.fakten_unveraendert)}; offene Vorschläge aus Widersprüchen: '
              f'{m.vorschlaege_offen}.',
              f'- Hinweise „ruhend“ im Rauschen (geprüft: jüngste Quelle älter als ein Jahr, kein Fehlalarm): '
              f'{m.rauschen_ruhend}.',
              f'- Art `veralteter_satz`: {"nicht gemessen (ohne Modell entsteht keine Lage)" if not m.lagen else f"{m.lagen} Lagen geprüft"}.',
              '', '| Art | Unterart | erwartete Quellen | gefunden |', '|---|---|---|---|']
    for e in m.erwartet:
        zeilen.append(f"| {e.art} | {e.unterart or '–'} | {', '.join(e.quellen)} | {ja(e.gefunden)} |")
    zeilen += ['', '### Gefundene Befunde (Text der Oberfläche)', '']
    zeilen += [f'- {e.art}: {e.text}' for e in m.erwartet if e.gefunden]
    if m.fehlalarme:
        zeilen += ['', '### Fehlalarme', '']
        zeilen += [f"- {art} {unterart}: {', '.join(quellen)}: {text}" for art, unterart, quellen, text in m.fehlalarme]
    return '\n'.join(zeilen) + '\n'
