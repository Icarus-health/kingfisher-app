"""Was der Nutzer der Welt selbst getan hat: Projekte angelegt, Quellen zugeordnet, Aussagen angenommen.

Alles über die Routen, die auch die Oberfläche nutzt (FORMAT.md, Felder `projekte`, `projekt`,
`angenommen`):

* Projekt anlegen: `POST /api/v1/projects`.
* Quelle einem Projekt zuordnen: `PUT /api/v1/episodes/{id}/project` (ein Klick unter der Quelle).
* Aussage annehmen: `POST /api/v1/memory/candidates` mit Beleg (Episode, Zitat, Digest), danach
  `POST /api/v1/memory/candidates/{id}/accept`. Das ist genau der Weg „Vorschlag, dann Annahme durch
  einen Menschen“; die Messlatte spielt hier den Menschen, der schon früher zugestimmt hat.

Läuft nach der Aufnahme und vor dem Nachführen der Bezüge. Ergebnis: Welt-Projekt-ID -> Projekt-ID
des Arbeitsbereichs (die Stufe Lint übersetzt damit `projekt:<Welt-ID>` in erwarteten Befunden).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HandlungsErgebnis:
    projekte: dict = field(default_factory=dict)
    """Welt-Projekt-ID -> Projekt-ID im Arbeitsbereich."""
    zugeordnet: int = 0
    angenommen: dict = field(default_factory=dict)
    """ID der angenommenen Aussage in der Welt -> Kennung der Aussage im Wissensbestand."""
    fehler: list = field(default_factory=list)


def ausfuehren(instanz, welten, episoden: dict) -> HandlungsErgebnis:
    """Legt die Projekte an, ordnet Quellen zu und nimmt Aussagen an. `episoden`: Welt-ID -> Episoden-ID."""
    ergebnis = HandlungsErgebnis()
    for welt in welten:
        for projekt in welt.arbeitsprojekte:
            angelegt = instanz.anfrage('POST', '/api/v1/projects', {'name': projekt.name})
            ergebnis.projekte[projekt.id] = angelegt['id']
    for welt in welten:
        for quelle in welt.quellen:
            if quelle.projekt is None:
                continue
            episode_id = episoden.get(quelle.id)
            if episode_id is None:
                ergebnis.fehler.append(f'{quelle.id}: nicht aufgenommen, keine Zuordnung')
                continue
            instanz.anfrage('PUT', f'/api/v1/episodes/{episode_id}/project',
                            {'project_id': ergebnis.projekte[quelle.projekt]})
            ergebnis.zugeordnet += 1
    for welt in welten:
        for aussage in welt.angenommen:
            episode_id = episoden.get(aussage.beleg)
            if episode_id is None:
                ergebnis.fehler.append(f'{aussage.id}: Beleg {aussage.beleg} nicht aufgenommen')
                continue
            episode = instanz.episodes.get(episode_id)
            vorschlag = instanz.anfrage('POST', '/api/v1/memory/candidates', {
                'subject_ref': sache_der_welt(aussage.subjekt, ergebnis.projekte), 'predicate': aussage.praedikat,
                'value': aussage.wert, 'statement': aussage.aussage, 'rationale': 'Von Lea angenommen (Welt der Messlatte).',
                'evidence': [{'episode_id': episode_id, 'quote': aussage.zitat, 'digest': episode.digest}],
                'proposed_by': 'messlatte'})['candidate']
            aussage_im_bestand = instanz.anfrage('POST', f'/api/v1/memory/candidates/{vorschlag["id"]}/accept',
                                                 {'supersedes': []})
            ergebnis.angenommen[aussage.id] = aussage_im_bestand['id']
    return ergebnis


def sache_der_welt(sache: str, projekte: dict) -> str:
    """`projekt:<Welt-ID>` wird zur Kennung, die das Produkt für das angelegte Projekt nutzt."""
    art, _, kennung = sache.partition(':')
    if art == 'projekt' and kennung in projekte:
        return f'project:{projekte[kennung]}'
    return sache
