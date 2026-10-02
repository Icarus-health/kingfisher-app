"""Modus „lokal“: dieselben Bewertungen an der laufenden Instanz des Nutzers.

    python -m messlatte lokal --fragen DATEI.json [--adresse http://127.0.0.1:8890] [--zeigen]

Die Fragen stammen aus einer Datei im Fragenformat von FORMAT.md (`belege` sind
dort optional und werden hier ignoriert: Es gibt keine Welt, gegen die man sie
prüfen könnte). Gefragt wird die **laufende** Instanz über HTTP, über dieselbe
Konversations-API wie die Oberfläche.

**Datenschutz:** Der Bericht dieses Modus enthält nur IDs, Kategorien, Ergebnis-
klassen, Zähler und Zeiten. Keine Frage, keine Antwort, keine Quelle, keine
erwartete oder verbotene Aussage steht in einer Datei. Wer ihn weitergibt, gibt
nichts Persönliches weiter. `--zeigen` schreibt Antworten nur ins Terminal.

**Nebenwirkung:** Jede Frage legt in der Instanz ein Gespräch mit dem Titel
„Messlatte“ an; die Fragen werden dort als Gesprächsquellen festgehalten, wie
jede Frage im Betrieb. Die API bietet keinen Weg, Gespräche zu löschen.

Dieses Modul importiert das Produkt nicht; es braucht nur `httpx`.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, Protocol

from . import antwort as antwort_stufe
from . import zeiten as antwortzeit
from .bewertung import AntwortBewertung, Auswertung, aggregiere, bewerte_antwort, x_von_n
from .darstellung import WURZEL, git_stand, klassen_tabelle, tabelle, zeiten, zeiten_satz
from .daten import Erwartet, Frage, Verboten
from .ergebnisse import AntwortErgebnis
from .welt import WeltFehler, pruefe_fragen_lokal

TOKEN_NAME = 'ICARUS_SIDECAR_TOKEN'
STANDARD_ADRESSE = 'http://127.0.0.1:8890'
GESPRAECH_TITEL = 'Messlatte'


class VerbindungsFehler(Exception):
    """Die Instanz war nicht erreichbar oder hat die Anfrage abgelehnt; mit lesbarer Erklärung."""


class KeineInstanz(VerbindungsFehler):
    """Nicht erreichbar oder Token abgelehnt: Ohne Instanz gibt es nichts zu messen, der Lauf endet."""


class AnfrageAbgelehnt(VerbindungsFehler):
    """Die Instanz läuft, lehnt aber diese eine Anfrage ab: Die Frage zählt als Fehler, die nächste geht weiter."""


class Transport(Protocol):
    """Was `messen` von der Verbindung braucht. Ein `httpx.Client` erfüllt es, auch der TestClient."""

    def request(self, method: str, url: str, **kwargs): ...


def lese_token(wurzel: Path = WURZEL, umgebung: Mapping[str, str] | None = None) -> str | None:
    """Token aus der Umgebung, sonst aus `.kingfisher.env` (Zeile `ICARUS_SIDECAR_TOKEN=…`, wie `make start`)."""
    umgebung = os.environ if umgebung is None else umgebung
    if umgebung.get(TOKEN_NAME):
        return umgebung[TOKEN_NAME].strip()
    datei = wurzel / '.kingfisher.env'
    try:
        for zeile in datei.read_text(encoding='utf-8').splitlines():
            name, _, wert = zeile.partition('=')
            if name.strip() == TOKEN_NAME and wert.strip():
                return wert.strip().strip('"\'')
    except OSError:
        return None
    return None


def oeffne(adresse: str, token: str | None):
    """Ein `httpx.Client` mit Token-Kopf. Ohne Token wird nichts gesendet, das Produkt entscheidet."""
    import httpx
    kopf = {'X-Icarus-Token': token} if token else {}
    # trust_env=False: Die Instanz läuft auf diesem Rechner; ein Umgebungs-Proxy hat dort nichts zu suchen.
    return httpx.Client(base_url=adresse, headers=kopf, timeout=300.0, trust_env=False)


def _anfrage(transport: Transport, methode: str, pfad: str, daten: dict | None = None) -> dict:
    try:
        antwort = transport.request(methode, pfad, **({'json': daten} if daten is not None else {}))
    except Exception as fehler:  # noqa: BLE001 - httpx-Fehlerklassen sollen hier nicht durchschlagen
        raise KeineInstanz(f'Keine laufende Instanz erreichbar ({type(fehler).__name__}). '
                           'Läuft Kingfisher (`make start`) und stimmt --adresse?') from fehler
    if antwort.status_code in (401, 403):
        raise KeineInstanz('Die Instanz lehnt das Token ab. Prüfe .kingfisher.env oder die Umgebungsvariable '
                           f'{TOKEN_NAME}.')
    if antwort.status_code >= 400:
        raise AnfrageAbgelehnt(f'Die Instanz antwortet mit Status {antwort.status_code} auf {methode} {pfad}.')
    return antwort.json()


def _ohne_belege(frage: Frage) -> Frage:
    """Belege lassen sich ohne Welt nicht zuordnen; sie würden jede Antwort unvollständig aussehen lassen."""
    return replace(frage, erwartet=Erwartet(frage.erwartet.verhalten, frage.erwartet.aussagen,
                                            frage.erwartet.bedeutungen, ()),
                   verboten=Verboten(frage.verboten.aussagen, ()))


def frage_stellen(transport: Transport, frage: Frage, *, kalt: bool = False) -> AntwortErgebnis:
    """Eine Frage über die Konversations-API. Ein Fehler der Instanz wird zum Ergebnisfehler, nicht zur Ausnahme."""
    start = time.perf_counter()
    try:
        gespraech = _anfrage(transport, 'POST', '/api/v1/conversations', {'title': GESPRAECH_TITEL})['conversation']['id']
        antwort = _anfrage(transport, 'POST', f'/api/v1/conversations/{gespraech}/messages',
                           {'message': frage.frage, 'answer_mode': 'auto'})
        nachricht = antwort_stufe.antwort_nachricht(antwort)
    except (AnfrageAbgelehnt, ValueError) as fehler:
        return AntwortErgebnis(frage_id=frage.id, kalt=kalt, dauer_s=round(time.perf_counter() - start, 3),
                               fehler=str(fehler))
    gelesen = antwort_stufe.lese_nachricht(nachricht, {})
    return AntwortErgebnis(frage_id=frage.id, dauer_s=round(time.perf_counter() - start, 3), kalt=kalt, **gelesen)


@dataclass(frozen=True)
class LokalErgebnis:
    kopf: dict
    fragen: tuple  # (Frage, AntwortErgebnis, AntwortBewertung)
    auswertung: Auswertung


def messen(transport: Transport, fragen: tuple, *,
           zeigen: Callable[[Frage, AntwortErgebnis], None] | None = None) -> LokalErgebnis:
    """Stellt alle Fragen der laufenden Instanz und bewertet die Antworten. Kein Text gelangt ins Ergebnis."""
    ergebnisse = []
    for nummer, frage in enumerate(fragen):
        antwort = frage_stellen(transport, frage, kalt=nummer == 0)
        if zeigen is not None:
            zeigen(frage, antwort)
        ergebnisse.append((frage, antwort, bewerte_antwort(_ohne_belege(frage), antwort)))
    auswertung = aggregiere((f, b) for f, _, b in ergebnisse)
    kopf = {'modus': 'lokal', 'commit': git_stand(), 'datum': datetime.now().astimezone().isoformat(timespec='seconds'),
            'fragen': len(fragen), 'herkunft': 'laufende Instanz'}
    return LokalErgebnis(kopf, tuple(ergebnisse), auswertung)


# -- Bericht ohne Inhalte --------------------------------------------------------------------


def _antwortzeit(ergebnis: LokalErgebnis) -> dict:
    """Median und 90-%-Wert je Stufe der Antworten der Instanz und das Ziel (nur Zahlen)."""
    return antwortzeit.auswerten([], [r[1] for r in ergebnis.fragen])


def zu_dict(ergebnis: LokalErgebnis) -> dict:
    """Nur IDs, Klassen, Zähler, Zeiten. Absichtlich ohne Texte und ohne die erwarteten Aussagen."""
    def eintrag(frage: Frage, antwort: AntwortErgebnis, bewertung: AntwortBewertung) -> dict:
        return {'id': frage.id, 'kategorie': frage.kategorie, 'schwere': frage.schwere, 'klasse': bewertung.klasse,
                'erkannt': bewertung.erkannt, 'status': antwort.status, 'dauer_s': antwort.dauer_s, 'kalt': antwort.kalt,
                'zeiten': antwort.zeiten,
                'falsche_aussage': bewertung.falsche_aussage,
                'fehlende_pflichtaussagen': len(bewertung.fehlende_aussagen),
                'fehlende_bedeutungen': len(bewertung.fehlende_bedeutungen), 'fehler': bool(antwort.fehler)}
    a = ergebnis.auswertung
    return {'kopf': ergebnis.kopf,
            'auswertung': {'gesamt': asdict(a.gesamt), 'je_kategorie': {k: asdict(v) for k, v in a.je_kategorie.items()},
                           'je_schwere': {k: asdict(v) for k, v in a.je_schwere.items()},
                           'kritisch_nicht_richtig': list(a.kritisch_nicht_richtig)},
            'zeiten': zeiten([r[1].dauer_s for r in ergebnis.fragen if r[1].kalt],
                             [r[1].dauer_s for r in ergebnis.fragen if not r[1].kalt]),
            'antwortzeit': _antwortzeit(ergebnis),
            'fragen': [eintrag(*r) for r in ergebnis.fragen]}


def markdown(ergebnis: LokalErgebnis) -> str:
    g = ergebnis.auswertung.gesamt
    a = ergebnis.auswertung
    zeilen = ['# Messlatte lokal: Bericht ohne Inhalte', '',
              'Dieser Bericht enthält keine Fragen, Antworten oder Quellen, nur IDs, Klassen, Zähler und Zeiten.', '']
    zeilen += tabelle(['Kopf', ''], [['Commit', ergebnis.kopf['commit']], ['Herkunft', ergebnis.kopf['herkunft']],
                                     ['Datum der Messung', ergebnis.kopf['datum']], ['Fragen', ergebnis.kopf['fragen']]])
    zeilen += ['## Ergebnis auf einen Blick', '',
               f'- **Falsche Aussagen: {x_von_n(g.falsche_aussagen, g.n)} Antworten**',
               f'- **Richtig: {x_von_n(g.richtig, g.n)} Antworten**',
               '- **Nicht gemessen: 0 Fragen**']
    if a.kritisch_nicht_richtig:
        zeilen.append(f'- **Kritische Fragen, die nicht richtig waren:** {", ".join(a.kritisch_nicht_richtig)}')
    zeilen.append('- **' + antwortzeit.ziel_zeile(_antwortzeit(ergebnis)) + '**')
    zeilen += ['', '## Je Kategorie', ''] + klassen_tabelle('Kategorie', a.je_kategorie)
    zeilen += ['## Je Schwere', ''] + klassen_tabelle('Schwere', a.je_schwere)
    zeit = zeiten([r[1].dauer_s for r in ergebnis.fragen if r[1].kalt], [r[1].dauer_s for r in ergebnis.fragen if not r[1].kalt])
    zeilen += [zeiten_satz(zeit), '', '## Antwortzeit', ''] + antwortzeit.markdown(_antwortzeit(ergebnis))
    zeilen += ['## Je Frage', '']
    zeilen += tabelle(['ID', 'Kategorie', 'Schwere', 'Klasse', 'Erkannt', 'Status', 'Sekunden'],
                      [[f.id, f.kategorie, f.schwere, b.klasse + (' · FALSCHE AUSSAGE' if b.falsche_aussage else ''),
                        b.erkannt, an.status, an.dauer_s] for f, an, b in ergebnis.fragen])
    return '\n'.join(zeilen)


def lade_fragen(pfad: Path) -> tuple:
    """Fragen-Datei lesen und prüfen. Wirft `WeltFehler` mit lesbaren Meldungen."""
    try:
        daten = json.loads(Path(pfad).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise WeltFehler([f'{pfad}: Datei fehlt.']) from None
    except (UnicodeDecodeError, json.JSONDecodeError) as fehler:
        raise WeltFehler([f'{pfad}: Kein gültiges JSON in UTF-8 ({fehler}).']) from None
    return pruefe_fragen_lokal(daten, str(pfad))
