"""Akten als Markdown-Ordner (M2): nur lesend, für Obsidian oder jeden Editor.

Die Akten liegen in SQLite und sind nur in der Oberfläche sichtbar. Dieses Modul legt sie
als lesbaren, verlinkten Ordner ab, damit der Nutzer sie dort hat, wo er ohnehin schreibt.
**Nichts fließt zurück:** Der Ordner wird bei jedem Schreiben neu erzeugt und überschrieben;
keine Zeile daraus wird je gelesen, weder von den Akten noch vom Gedächtnis.

Aufbau des Ordners:

* `index.md`: Katalog aller Akten nach Art, mit Stand-Datum.
* `Personen/`, `Organisationen/`, `Projekte/`, `Themen/`, `Orte/`: je Akte eine Datei mit
  Frontmatter (`art`, `sache_id`, `stand`, `kingfisher_version`), der Lage (nur geprüfte Sätze),
  Stand, Verlauf, offenen Punkten, Fristen, Terminen, Aufgaben und den Beziehungen als
  `[[Wiki-Link]]` und als gewöhnlicher Markdown-Link. Jeder Satz trägt einen Belegverweis:
  Titel und Datum der Quelle und `kingfisher://quelle/<id>`.
* `Quellen/<id>.md` nur, wenn der Nutzer „Quellen mitschreiben“ einschaltet. Das ist der
  Rohtext der Quelle und deshalb Vorgabe aus.
* `_README.md`: erzeugt von Kingfisher, wird überschrieben, Änderungen fließen nicht zurück,
  der Ordner enthält Klartext.
* `.kingfisher-akten`: Marke. Nur ein Ordner mit dieser Marke darf beim nächsten Schreiben
  ersetzt werden (siehe `scripts/mac_folder_worker.py`).

**Deterministisch:** Gleicher Bestand und gleicher Tag ergeben byte-gleiche Dateien. Nichts darin
hängt von der Uhrzeit des Schreibens, von Zufall oder von der Reihenfolge der Datenbank ab.
**Sichere Namen:** keine Pfadtrennzeichen, keine Zeichen, die Obsidian oder ein Dateisystem ablehnt,
begrenzte Länge, Kollisionen (auch solche nur in der Schreibweise) bekommen ein festes Suffix.

Dieses Modul kennt keinen Server. Es bekommt fertige Akten (`AkteIn`) und zwei Nachschlagefunktionen
für Quellen und liefert `{relativer Pfad: Text}`; `schreiben` legt das atomar ab.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
from urllib.parse import quote

from . import atomic, datumstext

MARKE = '.kingfisher-akten'
#: Name des Unterordners, den der Mac-Helfer im gewählten Ordner anlegt; nur er wird je ersetzt.
ORDNERNAME = 'Kingfisher Akten'
#: Reihenfolge und Ordnernamen der Arten, so wie der Nutzer sie liest.
ART_ORDNER = {'person': 'Personen', 'organisation': 'Organisationen', 'projekt': 'Projekte',
              'thema': 'Themen', 'ort': 'Orte'}
ART_REIHE = tuple(ART_ORDNER)
QUELLEN_ORDNER = 'Quellen'
#: Längster Dateiname (ohne Endung) in Bytes; gängige Dateisysteme erlauben 255 für den ganzen Namen.
MAX_NAME_BYTES = 100
#: Ein Rohtext über dieser Länge wird sichtbar gekürzt (nie still).
MAX_QUELLTEXT = 500_000

_VERBOTEN = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f\x7f]')
_RESERVIERT = frozenset({'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
                         *(f'lpt{i}' for i in range(1, 10))})
_GRUND = {'absage': 'abgesagt', 'erledigt': 'erledigt', 'aufgabe_erledigt': 'Aufgabe erledigt',
          'aufgabe_verworfen': 'Aufgabe verworfen'}


# -- Eingaben --

@dataclass(frozen=True)
class AkteIn:
    """Eine Akte mit ihrer Lage, so wie die Oberfläche sie bekommt (`Akten.akte`, `Lagen.lage`)."""

    sache: str
    art: str
    name: str
    akte: dict[str, Any]
    lage: dict[str, Any] | None = None


# -- Kleinteile --

def dateiname(name: str) -> str:
    """Ein sicherer Dateiname (ohne Endung): keine Pfadtrennzeichen, keine Steuer- oder Linkzeichen, begrenzt."""
    text = unicodedata.normalize('NFC', name or '')
    text = ' '.join(_VERBOTEN.sub(' ', text).split()).strip('. ')
    text = _kuerzen(text, MAX_NAME_BYTES)
    if not text:
        text = 'Ohne Name'
    if text.casefold() in _RESERVIERT:
        text += '_'
    return text


def _kuerzen(text: str, max_bytes: int) -> str:
    while len(text.encode('utf-8')) > max_bytes:
        text = text[:-1]
    return text.rstrip('. ')


def _kurz(text: Any) -> str:
    """Eine Zeile aus beliebigem Text, Klammern entschärft (sie würden einen Link zerreißen)."""
    return ' '.join(str(text or '').split()).replace('[', '(').replace(']', ')')


def _yaml(wert: Any) -> str:
    """Ein Wert für das Frontmatter. JSON ist gültiges YAML; Datumswerte stehen bewusst ohne Anführungszeichen."""
    if isinstance(wert, date):
        return wert.isoformat()
    return json.dumps(wert, ensure_ascii=False)


def frontmatter(felder: Iterable[tuple[str, Any]]) -> str:
    return '---\n' + ''.join(f'{schluessel}: {_yaml(wert)}\n' for schluessel, wert in felder) + '---\n\n'


def _zone():
    from .model import user_timezone
    return user_timezone() or timezone.utc


def tag(wert: Any) -> str:
    """Ein Datum als TT.MM.JJJJ in der Zeit des Nutzers; leer, wenn es nichts Lesbares ist."""
    if not wert:
        return ''
    moment = datumstext.iso_versuchen(wert)
    if moment is None:
        return ''
    if moment.tzinfo is not None:
        moment = moment.astimezone(_zone())
    return moment.strftime('%d.%m.%Y')


def iso_tag(wert: Any) -> str:
    """Ein Datum als JJJJ-MM-TT (für das Frontmatter; Dataview liest es als Datum)."""
    text = tag(wert)
    return f'{text[6:]}-{text[3:5]}-{text[:2]}' if text else ''


def _link_pfad(pfad: str) -> str:
    return quote(pfad, safe='/')


# -- Namen und Pfade --

def pfade_vergeben(akten: list[AkteIn]) -> dict[str, str]:
    """Sache -> relativer Pfad (`Personen/Anna Keller.md`), stabil und ohne Kollision.

    Die Reihenfolge der Vergabe folgt Art, Name und Kennung, nicht der Datenbank: Bei einer Kollision
    behält der erste den schlichten Namen, die übrigen tragen ein Suffix aus ihrer Kennung (`Name (a1b2c3)`).
    Verglichen wird ohne Groß-/Kleinschreibung, weil der Mac sie nicht unterscheidet.
    """
    belegt: dict[str, set[str]] = {ordner: set() for ordner in ART_ORDNER.values()}
    ergebnis: dict[str, str] = {}
    rang = {art: i for i, art in enumerate(ART_REIHE)}
    for eintrag in sorted(akten, key=lambda e: (rang.get(e.art, 99), e.name.casefold(), e.sache)):
        ordner = ART_ORDNER.get(eintrag.art, 'Sonstiges')
        genutzt = belegt.setdefault(ordner, set())
        basis = dateiname(eintrag.name)
        name = basis
        laenge = 6
        kennung = hashlib.sha256(eintrag.sache.encode('utf-8')).hexdigest()
        while name.casefold() in genutzt:
            name = f'{_kuerzen(basis, MAX_NAME_BYTES - 10)} ({kennung[:laenge]})'
            laenge += 2
        genutzt.add(name.casefold())
        ergebnis[eintrag.sache] = f'{ordner}/{name}.md'
    return ergebnis


def quellen_dateiname(episode_id: str) -> str:
    """Dateiname einer Quelle: die Kennung, wo sie schon sicher ist, sonst mit Hash gesichert."""
    sicher = re.sub(r'[^A-Za-z0-9._-]', '_', episode_id)[:80] or 'quelle'
    if sicher != episode_id or sicher.startswith('.'):
        sicher = sicher.lstrip('.') + '-' + hashlib.sha256(episode_id.encode('utf-8')).hexdigest()[:8]
    return sicher


# -- Darstellung --

class _Schreiber:
    """Baut alle Dateien. Hält die Nachschlagetabellen, damit jede Datei dieselben Links setzt."""

    def __init__(self, akten: list[AkteIn], *, stand: date, version: str,
                 info: Callable[[str], dict[str, Any] | None],
                 text: Callable[[str], str | None] | None) -> None:
        self.akten = sorted(akten, key=lambda e: (ART_REIHE.index(e.art) if e.art in ART_REIHE else 99,
                                                   e.name.casefold(), e.sache))
        self.stand, self.version, self.info, self.text = stand, version, info, text
        self.quellen_an = text is not None
        self.pfade = pfade_vergeben(akten)
        self.zitiert: dict[str, set[str]] = {}          # Quelle -> Sachen, die sie nennen

    # -- Links --

    @staticmethod
    def _wiki(pfad: str, beschriftung: str) -> str:
        ziel = pfad[:-3] if pfad.endswith('.md') else pfad
        # Im Alias trennt `|` den Anzeigetext ab; ein zweiter würde den Link zerreißen.
        return f'[[{ziel}|{_kurz(beschriftung).replace("|", "/")}]]'

    def _md(self, pfad: str, beschriftung: str, von: str) -> str:
        tiefe = len(PurePosixPath(von).parts) - 1
        return f'[{_kurz(beschriftung)}]({_link_pfad("../" * tiefe + pfad)})'

    def _verweis(self, pfad: str, beschriftung: str, von: str) -> str:
        return f'{self._wiki(pfad, beschriftung)} ({self._md(pfad, beschriftung, von)})'

    def _beleg(self, episode_id: str, von: str, sache: str | None, titel: Any = None, datum: Any = None) -> str:
        """Der Belegverweis: Titel, Datum, `kingfisher://quelle/<id>` und, wo mitgeschrieben, der Pfad."""
        gefunden = self.info(episode_id) or {}
        titel = _kurz(titel or gefunden.get('titel') or episode_id)
        datum_text = tag(datum or gefunden.get('datum'))
        if sache is not None:
            self.zitiert.setdefault(episode_id, set()).add(sache)
        teile = [f'Quelle: {titel}' + (f', {datum_text}' if datum_text else ''),
                 f'[kingfisher://quelle/{_link_kennung(episode_id)}](kingfisher://quelle/{_link_kennung(episode_id)})']
        if self.quellen_an:
            pfad = f'{QUELLEN_ORDNER}/{quellen_dateiname(episode_id)}.md'
            teile.append(f'{self._wiki(pfad, titel)} ({self._md(pfad, pfad, von)})')
        return ' · '.join(teile)

    def _zeile_beleg(self, zeile: dict[str, Any], von: str, sache: str) -> str:
        return self._beleg(zeile['episode_id'], von, sache, zeile.get('titel'),
                           zeile.get('occurred_at') or zeile.get('recorded_at'))

    # -- Akte --

    def akte_datei(self, e: AkteIn) -> str:
        pfad = self.pfade[e.sache]
        a = e.akte
        # Kreis (Person) und private Art (Organisation) nur, wie ein Mensch sie bestätigt hat (M4).
        zusatz = [('kreis', a.get('kreis') or 'unbestimmt')] if e.art == 'person' else \
            [('akten_art', a['akten_art'])] if a.get('akten_art') else []
        kopf = frontmatter([('art', e.art), ('sache_id', e.sache), ('name', e.name), *zusatz, ('stand', self.stand),
                            ('kingfisher_version', self.version), ('quellen', a['quellen']['gesamt'])])
        teile = [kopf, f'# {_kurz(e.name)}\n\n',
                 f'{a["art_text"]} · Stand {self.stand.strftime("%d.%m.%Y")} · '
                 f'{self._md("index.md", "zum Katalog", pfad)} · {self._wiki("index", "Katalog")}\n\n'
                 '> Erzeugt von Kingfisher, nur zum Lesen. Änderungen hier fließen nicht zurück.\n\n']
        if a['quellen'].get('begrenzt'):
            teile.append(f'> Ausgewertet sind die jüngsten {a["quellen"]["beruecksichtigt"]} von '
                         f'{a["quellen"]["gesamt"]} Quellen.\n\n')
        for abschnitt in (self._lage(e, pfad), self._stand_der_dinge(e, pfad), self._offen(e, pfad),
                          self._fristen(e, pfad), self._termine(e, pfad), self._aufgaben(e),
                          self._verlauf(e, pfad), self._beziehungen(e, pfad)):
            if abschnitt:
                teile.append(abschnitt + '\n')
        return ''.join(teile).rstrip('\n') + '\n'

    def _lage(self, e: AkteIn, pfad: str) -> str:
        zeilen = ['## Lage\n\n']
        lage = e.lage
        if not lage or not lage.get('saetze'):
            zeilen.append('Noch keine Lage. Sie entsteht im Hintergrund mit einem lokalen Modell; '
                          'bis dahin tragen Stand, Verlauf und offene Punkte die Akte.\n')
            return ''.join(zeilen)
        zeilen.append(f'Nur geprüfte Sätze: Jeder stützt sich auf mindestens eine Quelle. '
                      f'Stand der Lage: {tag(lage.get("stand_vom") or lage.get("erstellt_am"))}.\n')
        if lage.get('veraltet'):
            zeilen.append('Neue Quellen sind seitdem dazugekommen; die Lage wird aktualisiert.\n')
        zeilen.append('\n')
        for satz in lage['saetze']:
            belege = '; '.join(f'[{b["nummer"]}] ' + self._beleg(b['episode_id'], pfad, e.sache, b.get('titel'))
                               for b in satz['belege'])
            zeilen.append(f'- {_kurz(satz["text"])}\n  - {belege}\n')
        return ''.join(zeilen)

    def _eintrag(self, zeile: dict[str, Any], pfad: str, sache: str, *, vorne: str = '') -> str:
        text = _kurz(zeile.get('text'))
        return (f'- {vorne}{"„" + text + "“" if text else ""}\n'
                f'  - {self._zeile_beleg(zeile, pfad, sache)}\n')

    def _stand_der_dinge(self, e: AkteIn, pfad: str) -> str:
        stand = e.akte['stand_der_dinge']
        if not stand['aktuell']:
            return ''
        gruppen = [(stand['aktuell'], stand['vorher'], stand['vorher_gesamt']),
                   *((g['aktuell'], g['vorher'], g['vorher_gesamt']) for g in stand['weitere'])]
        zeilen = ['## Stand\n\nJe Gegenstand die jüngste Meldung; Älteres steht darunter als „vorher“.\n\n']
        for aktuell, vorher, vorher_gesamt in gruppen:
            zeilen.append(self._eintrag(aktuell, pfad, e.sache, vorne=f'**{aktuell["art"]}**, {tag(aktuell.get("occurred_at") or aktuell.get("recorded_at"))}: '))
            for alt in vorher:
                text = _kurz(alt.get('text'))
                zeilen.append(f'  - vorher ({tag(alt.get("occurred_at") or alt.get("recorded_at"))}): „{text}“ — '
                              f'{self._zeile_beleg(alt, pfad, e.sache)}\n')
            if vorher_gesamt > len(vorher):
                zeilen.append(f'  - … und {vorher_gesamt - len(vorher)} weitere ältere Meldungen\n')
        return ''.join(zeilen)

    def _offen(self, e: AkteIn, pfad: str) -> str:
        offen = e.akte['offen']
        if not offen['eintraege'] and not offen['erledigt']['eintraege']:
            return ''
        zeilen = ['## Offene Punkte\n\nVermutlich offen: Bitten und Zusagen ohne spätere Erledigung oder Absage. '
                  'Kingfisher behauptet nicht, dass etwas offen ist.\n\n']
        if not offen['eintraege']:
            zeilen.append('Keine Bitte und keine Zusage gilt derzeit als offen.\n')
        for zeile in offen['eintraege']:
            zeilen.append(self._eintrag(zeile, pfad, e.sache,
                                        vorne=f'**{zeile["art"]}**, {tag(zeile.get("occurred_at") or zeile.get("recorded_at"))}: '))
            danach = zeile.get('danach_geaendert')
            if danach:
                zeilen.append(f'  - danach geändert: „{_kurz(danach.get("text"))}“ — {self._zeile_beleg(danach, pfad, e.sache)}\n')
            if zeile.get('aufgabe'):
                zeilen.append(f'  - Aufgabe dazu: {_kurz(zeile["aufgabe"]["title"])}\n')
        if offen['gesamt'] > len(offen['eintraege']):
            zeilen.append(f'- … und {offen["gesamt"] - len(offen["eintraege"])} weitere\n')
        if offen['erledigt']['eintraege']:
            zeilen.append('\n### Vermutlich erledigt\n\n')
            for zeile in offen['erledigt']['eintraege']:
                grund = _GRUND.get(zeile.get('grund'), 'erledigt')
                zeilen.append(self._eintrag(zeile, pfad, e.sache, vorne=f'**{zeile["art"]}** ({grund}): '))
                if zeile.get('durch'):
                    zeilen.append(f'  - erledigt laut: „{_kurz(zeile["durch"].get("text"))}“ — '
                                  f'{self._zeile_beleg(zeile["durch"], pfad, e.sache)}\n')
        return ''.join(zeilen)

    def _fristen(self, e: AkteIn, pfad: str) -> str:
        f = e.akte['fristen']
        if not (f['kommend'] or f['verstrichen'] or f['ersetzt'] or f['ohne_datum']['eintraege']):
            return ''
        zeilen = ['## Fristen\n\n']

        def liste(titel: str, eintraege: list[dict[str, Any]], *, ersetzt: bool = False) -> None:
            if not eintraege:
                return
            zeilen.append(f'### {titel}\n\n')
            for z in eintraege:
                satz = _kurz(z.get('satz') or z.get('text'))
                vorne = f'**{tag(z["datum"])}**: '
                zeilen.append(f'- {vorne}„{satz}“\n  - {self._zeile_beleg(z, pfad, e.sache)}\n')
                if ersetzt and z.get('ersetzt_durch'):
                    neu = z['ersetzt_durch']
                    zeilen.append(f'  - überholt, jetzt {tag(neu["datum"])}: „{_kurz(neu.get("ausdruck"))}“ — '
                                  f'{self._beleg(neu["episode_id"], pfad, e.sache)}\n')

        liste('Kommend', f['kommend'])
        liste('Verstrichen', f['verstrichen'])
        liste('Überholt', f['ersetzt'], ersetzt=True)
        if f['ohne_datum']['eintraege']:
            zeilen.append('### Zeitangaben ohne festes Datum\n\n')
            for z in f['ohne_datum']['eintraege']:
                zeilen.append(f'- „{_kurz(z["ausdruck"])}“\n  - {self._beleg(z["episode_id"], pfad, e.sache, z.get("titel"))}\n')
        return ''.join(zeilen)

    def _termine(self, e: AkteIn, pfad: str) -> str:
        t = e.akte['termine']
        if not (t['kommend'] or t['vergangen']):
            return ''
        zeilen = ['## Termine\n\n']
        for titel, liste in (('Kommend', t['kommend']), ('Vergangen', t['vergangen'])):
            if not liste:
                continue
            zeilen.append(f'### {titel}\n\n')
            for z in liste:
                ort = f', {_kurz(z["ort"])}' if z.get('ort') else ''
                zeilen.append(f'- **{tag(z["start"])}** {_kurz(z["titel"])}{ort}\n'
                              f'  - {self._beleg(z["episode_id"], pfad, e.sache, z["titel"], z["start"])}\n')
                if z.get('vermutlich_abgesagt'):
                    laut = z['vermutlich_abgesagt']
                    zeilen.append(f'  - vermutlich abgesagt laut: „{_kurz(laut.get("text"))}“ — {self._zeile_beleg(laut, pfad, e.sache)}\n')
        return ''.join(zeilen)

    @staticmethod
    def _aufgaben(e: AkteIn) -> str:
        a = e.akte['aufgaben']
        if not a['eintraege']:
            return ''
        zeilen = ['## Aufgaben\n\n']
        for z in a['eintraege']:
            faellig = f' (fällig {tag(z["due"])})' if z.get('due') else ''
            wartet = f', wartet auf {_kurz(z["wartet_auf"])}' if z.get('wartet_auf') else ''
            zeilen.append(f'- {_kurz(z["title"])}{faellig}{wartet}\n')
        if a['gesamt'] > len(a['eintraege']):
            zeilen.append(f'- … und {a["gesamt"] - len(a["eintraege"])} weitere\n')
        return ''.join(zeilen)

    def _verlauf(self, e: AkteIn, pfad: str) -> str:
        v = e.akte['verlauf']
        if not v['eintraege']:
            return ''
        zeilen = ['## Verlauf\n\nDie Quellen zur Sache, jüngste zuerst.\n\n']
        for z in v['eintraege']:
            titel = _kurz(z['titel'])
            text = _kurz(z.get('text'))
            grund = ', '.join({'anker': 'Adresse', 'modell': 'Erwähnung', 'nutzer': 'von dir zugeordnet'}.get(g, g)
                              for g in z.get('grundlagen', []))
            zeilen.append(f'- **{tag(z["datum"])}** {titel}' + (f' ({grund})' if grund else '') + '\n')
            if text:
                zeilen.append(f'  - {z.get("art") or "Auszug"}: „{text}“\n')
            zeilen.append(f'  - {self._beleg(z["episode_id"], pfad, e.sache, z["titel"], z["datum"])}\n')
        if v['gesamt'] > len(v['eintraege']):
            zeilen.append(f'- … und {v["gesamt"] - len(v["eintraege"])} weitere Quellen\n')
        return ''.join(zeilen)

    def _beziehungen(self, e: AkteIn, pfad: str) -> str:
        b = e.akte['beteiligte']
        if not b['eintraege']:
            return ''
        zeilen = ['## Beziehungen\n\nSachen, die in denselben Quellen vorkommen (Anzahl der gemeinsamen Quellen).\n\n']
        for z in b['eintraege']:
            ziel = self.pfade.get(z['sache'])
            anzahl = f'{z["anzahl"]} gemeinsame {"Quelle" if z["anzahl"] == 1 else "Quellen"}'
            zeilen.append(f'- {self._verweis(ziel, z["name"], pfad) if ziel else _kurz(z["name"])}, {anzahl}\n')
        if b['gesamt'] > len(b['eintraege']):
            zeilen.append(f'- … und {b["gesamt"] - len(b["eintraege"])} weitere\n')
        return ''.join(zeilen)

    # -- Katalog, Quellen, Hinweis --

    def index(self, letzte: dict[str, str | None]) -> str:
        kopf = frontmatter([('art', 'katalog'), ('stand', self.stand), ('kingfisher_version', self.version),
                            ('akten', len(self.akten))])
        teile = [kopf, '# Akten\n\n', f'Stand {self.stand.strftime("%d.%m.%Y")} · {len(self.akten)} Akten · '
                 f'{self._wiki("_README", "Hinweis")}\n\n']
        for art in ART_REIHE:
            gruppe = [e for e in self.akten if e.art == art]
            if not gruppe:
                continue
            teile.append(f'## {ART_ORDNER[art]} ({len(gruppe)})\n\n')
            for e in gruppe:
                pfad = self.pfade[e.sache]
                zuletzt = tag(letzte.get(e.sache))
                quellen = e.akte['quellen']['gesamt']
                teile.append(f'- {self._verweis(pfad, e.name, "index.md")}, {quellen} {"Quelle" if quellen == 1 else "Quellen"}'
                             + (f', zuletzt {zuletzt}' if zuletzt else '') + '\n')
            teile.append('\n')
        if not self.akten:
            teile.append('Noch keine Akten: Sie entstehen, sobald Kingfisher Quellen gelesen hat.\n')
        return ''.join(teile).rstrip('\n') + '\n'

    def readme(self) -> str:
        quellen = ('Der Ordner `Quellen/` enthält den **Rohtext** der Quellen (Mails, Notizen, Mitschriften), '
                   'weil du „Quellen mitschreiben“ eingeschaltet hast.\n' if self.quellen_an else
                   'Rohtexte der Quellen sind nicht dabei. Nur Auszüge und Verweise stehen in den Akten.\n')
        return (frontmatter([('art', 'hinweis'), ('stand', self.stand), ('kingfisher_version', self.version)])
                + '# Akten aus Kingfisher\n\n'
                  '- Dieser Ordner wurde von **Kingfisher** erzeugt.\n'
                  '- Er wird bei jedem Schreiben **überschrieben**. Eigene Notizen gehören nicht hierher, '
                  'sondern daneben.\n'
                  '- Änderungen hier **fließen nicht zurück**: Kingfisher liest aus diesem Ordner nichts. '
                  'Eine Korrektur machst du in Kingfisher selbst, dann steht sie beim nächsten Schreiben auch hier.\n'
                  '- Die Dateien enthalten **Klartext** aus deinen Mails, Terminen und Notizen. '
                  'Wer den Ordner lesen kann, liest das alles; er ist nicht verschlüsselt. Lege ihn nicht in einen '
                  'geteilten oder synchronisierten Ordner, dem du nicht traust.\n'
                  f'- {quellen}'
                  '- Jeder Satz nennt seine Quelle mit Titel, Datum und einem Verweis `kingfisher://quelle/<id>`.\n'
                  '- Die Dateien lassen sich in Obsidian öffnen (Wiki-Links und Frontmatter für Dataview) '
                  'und in jedem anderen Editor (gewöhnliche Markdown-Links).\n')

    def quelle_datei(self, episode_id: str) -> str | None:
        info = self.info(episode_id)
        roh = self.text(episode_id) if self.text else None
        if info is None or roh is None:
            return None
        pfad = f'{QUELLEN_ORDNER}/{quellen_dateiname(episode_id)}.md'
        kopf = frontmatter([('art', 'quelle'), ('quelle_id', episode_id), ('titel', _kurz(info.get('titel'))),
                            ('datum', iso_tag(info.get('datum'))), ('herkunft', info.get('art') or ''),
                            ('stand', self.stand), ('kingfisher_version', self.version)])
        gekuerzt = len(roh) > MAX_QUELLTEXT
        if gekuerzt:
            roh = roh[:MAX_QUELLTEXT]
        zaun = '`' * max(3, (max((len(m) for m in re.findall(r'`+', roh)), default=0)) + 1)
        gehoert = sorted(self.zitiert.get(episode_id, ()), key=lambda s: self.pfade.get(s, s))
        verweise = [self._verweis(self.pfade[s], next(a.name for a in self.akten if a.sache == s), pfad)
                    for s in gehoert if s in self.pfade]
        return (kopf + f'# {_kurz(info.get("titel")) or episode_id}\n\n'
                f'Quelle vom {tag(info.get("datum"))} · [kingfisher://quelle/{_link_kennung(episode_id)}]'
                f'(kingfisher://quelle/{_link_kennung(episode_id)})\n\n'
                + (f'Genannt in: {"; ".join(verweise)}\n\n' if verweise else '')
                + f'{zaun}text\n{roh}\n{zaun}\n'
                + ('\n> Der Text ist hier gekürzt; das Original liegt in Kingfisher.\n' if gekuerzt else ''))


def _link_kennung(episode_id: str) -> str:
    return quote(episode_id, safe='')


def bauen(akten: list[AkteIn], *, stand: date, version: str,
          info: Callable[[str], dict[str, Any] | None],
          text: Callable[[str], str | None] | None = None,
          letzte: dict[str, str | None] | None = None) -> dict[str, str]:
    """Alle Dateien des Ordners: `{relativer Pfad mit /: Text}`. Nichts wird geschrieben.

    `info(id)` liefert `titel`, `datum`, `art` einer Quelle (für den Belegverweis); `text(id)` den Rohtext
    und nur, wenn der Nutzer „Quellen mitschreiben“ eingeschaltet hat (sonst `None`: dann fehlt `Quellen/`).
    `letzte` ist je Sache das Datum der jüngsten Quelle (für den Katalog).
    """
    schreiber = _Schreiber(akten, stand=stand, version=version, info=info, text=text)
    dateien = {schreiber.pfade[e.sache]: schreiber.akte_datei(e) for e in schreiber.akten}
    dateien['index.md'] = schreiber.index(letzte or {})
    dateien['_README.md'] = schreiber.readme()
    if schreiber.quellen_an:
        for episode_id in sorted(schreiber.zitiert):
            inhalt = schreiber.quelle_datei(episode_id)
            if inhalt is not None:
                dateien[f'{QUELLEN_ORDNER}/{quellen_dateiname(episode_id)}.md'] = inhalt
    dateien[MARKE] = json.dumps({'erzeugt_von': 'Kingfisher', 'stand': stand.isoformat(), 'version': version,
                                 'dateien': len(dateien) + 1, 'quellen': schreiber.quellen_an},
                                ensure_ascii=False, sort_keys=True) + '\n'
    return dateien


# -- Schreiben --

def pruefe_pfade(dateien: dict[str, str]) -> None:
    """Jeder Pfad muss relativ, ohne `..` und ohne Leerteile sein; sonst ist es ein Programmfehler."""
    for pfad in dateien:
        teile = pfad.split('/')
        if '\\' in pfad or '\x00' in pfad or any(t in ('', '.', '..') for t in teile):
            raise ValueError(f'Unsicherer Pfad im Export: {pfad!r}')


def schreiben(ziel: str | Path, dateien: dict[str, str]) -> int:
    """Legt `dateien` atomar unter `ziel` ab: erst in einen Nachbarordner, dann tauschen. Gibt die Dateizahl zurück.

    Liest man `ziel` während des Schreibens, sieht man die alte oder die neue Fassung, nie eine halbe.
    Bei jedem Fehler wird der Nachbarordner entfernt und `ziel` bleibt unversehrt.
    """
    pruefe_pfade(dateien)
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    neu = Path(tempfile.mkdtemp(prefix=f'.{ziel.name}.neu-', dir=ziel.parent))
    try:
        for pfad, text in sorted(dateien.items()):
            datei = neu.joinpath(*PurePosixPath(pfad).parts)
            datei.parent.mkdir(parents=True, exist_ok=True)
            datei.write_text(text, encoding='utf-8', newline='\n')
        atomic.ordner_tauschen(neu, ziel)
    except BaseException:
        shutil.rmtree(neu, ignore_errors=True)
        raise
    return len(dateien)


def aufraeumen(ziel: str | Path) -> None:
    """Räumt Reste eines abgebrochenen Schreibens neben `ziel` weg (halbe Nachbarordner)."""
    ziel = Path(ziel)
    if not ziel.parent.is_dir():
        return
    for rest in ziel.parent.glob(f'.{ziel.name}.neu-*'):
        shutil.rmtree(rest, ignore_errors=True)


# -- Sammeln aus den Bausteinen des Servers --

def sammeln(akten: Any, bezuege: Any, lagen: Any, *, jetzt: datetime) -> tuple[list[AkteIn], dict[str, str | None], int]:
    """Alle Akten mit Lage, so wie die Oberfläche sie zeigt (`alle=True`), dazu die jüngste Quelle je Sache.

    Eine Akte, die sich nicht berechnen lässt, wird übersprungen und gezählt; ein Fehler darf den Ordner
    nicht verhindern. Gibt `(Akten, letzte, übersprungen)` zurück.
    """
    sachen: dict[str, dict[str, Any]] = {}
    offset = 0
    while True:
        seite = bezuege.sachen(limit=200, offset=offset)
        if not seite['sachen']:
            break
        for eintrag in seite['sachen']:
            sachen.setdefault(eintrag['sache'], eintrag)
        offset += len(seite['sachen'])
        if offset >= seite['gesamt']:
            break
    namen = bezuege.beschriftungen(sorted(sachen))
    ergebnis: list[AkteIn] = []
    uebersprungen = 0
    for sache in sorted(sachen):
        try:
            daten = akten.akte(sache, jetzt=jetzt, alle=True)
            if daten is None:
                continue
            lage = lagen.lage(sache, daten) if lagen is not None else None
        except Exception:  # noqa: BLE001 - eine kaputte Akte darf den Ordner nicht verhindern
            uebersprungen += 1
            continue
        ergebnis.append(AkteIn(sache=sache, art=sachen[sache]['art'], name=namen.get(sache) or daten['name'],
                               akte=daten, lage=lage))
    return ergebnis, {s: e.get('letzte') for s, e in sachen.items()}, uebersprungen


def quellen_lieferant(episodes: Any) -> tuple[Callable[[str], dict[str, Any] | None], Callable[[str], str | None]]:
    """`(info, text)` aus dem Episodenspeicher; Quellen, die nicht mehr gelten, liefern nichts."""
    def info(episode_id: str) -> dict[str, Any] | None:
        try:
            episode = episodes.get(episode_id)
        except Exception:  # noqa: BLE001
            return None
        moment = episode.occurred_at or episode.recorded_at
        return {'titel': episode.title, 'datum': moment.isoformat() if moment else None, 'art': episode.kind.value}

    def text(episode_id: str) -> str | None:
        try:
            if episode_id not in episodes.usable_ids([episode_id]):
                return None
            return episodes.get(episode_id).body
        except Exception:  # noqa: BLE001
            return None

    return info, text


__all__ = ['AkteIn', 'ART_ORDNER', 'MARKE', 'ORDNERNAME', 'aufraeumen', 'bauen', 'dateiname', 'frontmatter',
           'pfade_vergeben', 'quellen_dateiname', 'quellen_lieferant', 'sammeln', 'schreiben', 'tag']
