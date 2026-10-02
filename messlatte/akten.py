"""Stufe „Akten“ (D2): Enthält die Akte einer Sache die erwarteten Quellen und zeigt sie den NEUEN Stand?

Gemessen wird die Ebene 2 (`icarus_memory/akten.py`) an ausgewählten Szenarien der
vorhandenen Welt, ohne die Welt zu ändern und ohne Modell:

* **Quellen:** Steht jede erwartete Quelle im Verlauf der Sache? (Rückruf)
* **Aktuell:** Zeigen Stand, kommende Fristen und offene Punkte den neuen Wert?
* **Nicht aktuell:** Taucht der überholte Wert dort nicht auf, sondern nur unter
  „vorher“, „ersetzt“ oder „erledigt“? (Die schwere Regel: Aktualität schlägt Ähnlichkeit.)

**Lage (D3, optional):** Mit einem lokalen Modell für die Rolle „hintergrund“ (`--modell-hintergrund`)
erzeugt die Stufe zusätzlich die Lage (Ebene 3, `icarus_memory/lage.py`) jeder Sache und prüft sie an
denselben Erwartungen: Eine **verbotene Aussage** (der überholte Wert, `nicht_aktuell`) in einem Satz der
Lage, der ihn nicht als „vorher“ kennzeichnet, ist **falsch**. Die erwarteten Aussagen (`aktuell`) zeigen,
ob die Lage vollständig ist; fehlen sie, ist die Lage unvollständig, aber nicht falsch. Ohne Modell steht
die Lage als **nicht gemessen** im Bericht, nie als bestanden.

**Grenze:** Ebene 1 (die Art jedes Absatzes: Bitte, Zusage, Änderung …) liefert im
Betrieb ein lokales Modell. Hier ersetzt `RegelEinordnung` es durch feste
Schlüsselwortregeln. Die Stufe misst deshalb Bezüge, Verlauf, Fristen, Stand und
Erledigt-Erkennung **bei gegebener Einordnung**, nicht die Qualität der
Modelleinordnung. Ändert jemand die Regeln, ändert sich die Messung.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from icarus_memory.providers import ProviderError, Reply

# -- Einordnung ohne Modell -----------------------------------------------------

_GRUSS = re.compile(r'^(sehr geehrte|liebe[rn]?\b|guten (tag|morgen|abend)|hallo\b|mit freundlichen|beste grüße|'
                    r'viele grüße|herzliche grüße|freundliche grüße|ihr[e]? |tel\.|\d{2,}|ernährungsmanagement)', re.I)
_AENDERUNG = re.compile(r'verlänger|verschob|verschieb|neue[rnms]? (einreich|mailadresse|anschrift|frist)|'
                        r'ab jetzt|wechsle|geändert|abgesagt|absagen|absage\b|storniert|entfällt|nicht mehr|'
                        r'aktualisiert|nachhol|nachfolger', re.I)
# Ein Absatz mit Postleitzahl und Ort ist eine Anschrift: der Stand einer Angabe, nicht bloß ein Faktum.
_ANSCHRIFT = re.compile(r'\b\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+')
_ZUSAGE = re.compile(r'sage zu|zusage\b|wir stellen|lasse ich unterschreiben|bekommen sie von mir|kommt bis|'
                     r'ich schicke|ich übernehme|gern bin ich|bin ich .{0,30}dabei', re.I)
_BITTE = re.compile(r'\bbitte\b|können sie|könnten sie|würden sie|hätten sie', re.I)
_STAND = re.compile(r'anmeldungen|anmeldestand|bestätigen (ihre|die)|angekommen|erhalten\b', re.I)


class RegelEinordnung:
    """Ein „lokales Modell“, das Absätze nach Schlüsselwörtern einordnet. Kein Netzwerk, kein Modell."""

    name = 'messlatte'
    model = 'regel-einordnung'
    is_local = True
    supports_json = True

    def complete_json(self, messages, *, max_tokens: int = 256, schema=None) -> Reply:
        try:
            blocks = json.loads(messages[-1]['content'])['blocks']
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError('Unerwartete Einordnungsanfrage') from exc
        return Reply(text=json.dumps({'items': [{'block_id': b['block_id'], 'kind': self.art(b['text'])}
                                                for b in blocks]}), model=self.model)

    @staticmethod
    def art(text: str) -> str:
        if _GRUSS.match(text.strip()) and len(text) < 90:
            return 'irrelevant'
        for muster, art in ((_AENDERUNG, 'change'), (_ZUSAGE, 'commitment'), (_BITTE, 'request'), (_STAND, 'status'),
                            (_ANSCHRIFT, 'status')):
            if muster.search(text):
                return art
        return 'fact'

    def complete(self, messages, tools) -> Reply:
        raise ProviderError('Die Regel-Einordnung kennt nur complete_json.')


# -- Fälle -----------------------------------------------------------------------


@dataclass(frozen=True)
class Fall:
    """Eine Erwartung an die Akte einer Sache. Alle Verweise sind Welt-IDs beziehungsweise Textstücke."""

    id: str
    beschreibung: str
    sache: str
    quellen: tuple = ()
    """Welt-IDs, die im Verlauf der Sache stehen müssen."""
    aktuell: tuple = ()
    """Textstücke (Gruppen: mindestens eines je Gruppe), die in den aktuellen Aussagen stehen müssen."""
    nicht_aktuell: tuple = ()
    """Textstücke, die in den aktuellen Aussagen nicht stehen dürfen."""
    fruehere: tuple = ()
    """Textstücke, die unter „vorher“, „ersetzt“ oder „erledigt“ stehen müssen (der alte Wert bleibt nachvollziehbar)."""
    nicht_offen: tuple = ()
    """Welt-IDs, deren Bitte oder Zusage nicht als offen gelten darf."""
    abgesagte_termine: tuple = ()
    """Welt-IDs von Terminen, die als „vermutlich abgesagt“ gekennzeichnet sein müssen."""


FAELLE = (
    Fall('frist-verschoben-stiftung', 'Die Stiftung verschiebt die Einreichfrist: kommend ist der 12.11., nicht der 15.10.',
         sache='organisation:stiftungzgrm', quellen=('frist-verschoben-001', 'frist-verschoben-006',
                                                      'frist-verschoben-008', 'frist-verschoben-011'),
         aktuell=(('12. November 2026',),), nicht_aktuell=('15. Oktober 2026',)),
    Fall('frist-verschoben-klinik', 'Die Klinik sagt die Absichtserklärung bis 29.10. zu; kommende Frist in ihrer Akte.',
         sache='person:a:i.kaltenbach@klinik-taunushang.example',
         quellen=('frist-verschoben-003', 'frist-verschoben-010'), aktuell=(('29. Oktober',),)),
    Fall('adresse-geaendert-neu', 'Der neue Arbeitgeber trägt die neue Anschrift als Stand, nicht die alte.',
         sache='organisation:vitalzentrumkassel', quellen=('adresse-geaendert-008', 'adresse-geaendert-009'),
         aktuell=(('Lindenallee 22',),), nicht_aktuell=('Klinikstraße 5',)),
    Fall('adresse-geaendert-wechsel', 'Unter der alten Adresse ist der Wechsel mit der neuen Mailadresse der jüngste Stand.',
         sache='person:a:j.krueger@kreisklinik-rheingau.example',
         quellen=('adresse-geaendert-001', 'adresse-geaendert-003', 'adresse-geaendert-006'),
         aktuell=(('j.krueger@vitalzentrum-kassel.example',),), nicht_aktuell=('Klinikstraße 5',)),
    Fall('zusage-abgesagt-akademie', 'Die Absage steht als Stand; die frühere Zusage gilt nicht mehr als offen.',
         sache='organisation:akademietaunus',
         quellen=('zusage-abgesagt-001', 'zusage-abgesagt-002', 'zusage-abgesagt-003', 'zusage-abgesagt-008'),
         aktuell=(('absagen', 'abgesagt', 'Absage'),), nicht_offen=('zusage-abgesagt-002',),
         fruehere=('sage zu',), abgesagte_termine=('zusage-abgesagt-003',)),
)


@dataclass
class FallErgebnis:
    id: str
    beschreibung: str
    quellen_erwartet: int = 0
    quellen_gefunden: int = 0
    fehlende_quellen: list = field(default_factory=list)
    aktuell_ok: bool = True
    nicht_aktuell_ok: bool = True
    fruehere_ok: bool = True
    nicht_offen_ok: bool = True
    termine_ok: bool = True
    hinweise: list = field(default_factory=list)
    quellen_gesamt: int = 0
    dauer_ms: float = 0.0

    @property
    def bestanden(self) -> bool:
        return (not self.fehlende_quellen and self.aktuell_ok and self.nicht_aktuell_ok
                and self.fruehere_ok and self.nicht_offen_ok and self.termine_ok)


def aktuelle_texte(akte: dict) -> list[str]:
    """Alles, was die Akte als heutigen Stand behauptet: Stand, kommende Fristen, offene Punkte."""
    texte = []
    stand = akte['stand_der_dinge']
    if stand['aktuell']:
        texte.append(stand['aktuell']['text'])
    texte += [g['aktuell']['text'] for g in stand['weitere']]
    texte += [f['text'] for f in akte['fristen']['kommend']]
    texte += [o['text'] for o in akte['offen']['eintraege']]
    return texte


def fruehere_texte(akte: dict) -> list[str]:
    texte = [z['text'] for z in akte['stand_der_dinge']['vorher']]
    texte += [f['text'] for f in akte['fristen']['ersetzt'] + akte['fristen']['verstrichen']]
    texte += [e['text'] for e in akte['offen']['erledigt']['eintraege']]
    return texte


def pruefe(akte: dict | None, fall: Fall, welt_zu_episode: dict, episode_zu_welt: dict) -> FallErgebnis:
    ergebnis = FallErgebnis(fall.id, fall.beschreibung, quellen_erwartet=len(fall.quellen))
    if akte is None:
        ergebnis.fehlende_quellen = list(fall.quellen)
        ergebnis.aktuell_ok = not fall.aktuell
        ergebnis.hinweise.append('Keine Akte zu dieser Sache.')
        return ergebnis
    ergebnis.quellen_gesamt = akte['quellen']['gesamt']
    im_verlauf = {episode_zu_welt.get(e['episode_id']) for e in akte['verlauf']['eintraege']}
    ergebnis.fehlende_quellen = [q for q in fall.quellen if q not in im_verlauf]
    ergebnis.quellen_gefunden = len(fall.quellen) - len(ergebnis.fehlende_quellen)
    aktuell = ' \n'.join(aktuelle_texte(akte))
    for gruppe in fall.aktuell:
        if not any(stueck.casefold() in aktuell.casefold() for stueck in gruppe):
            ergebnis.aktuell_ok = False
            ergebnis.hinweise.append(f'Aktuell fehlt: {" | ".join(gruppe)}')
    for stueck in fall.nicht_aktuell:
        if stueck.casefold() in aktuell.casefold():
            ergebnis.nicht_aktuell_ok = False
            ergebnis.hinweise.append(f'Als aktuell gezeigt, aber überholt: {stueck}')
    frueher = ' \n'.join(fruehere_texte(akte))
    for stueck in fall.fruehere:
        if stueck.casefold() not in frueher.casefold():
            ergebnis.fruehere_ok = False
            ergebnis.hinweise.append(f'Unter „vorher/erledigt“ fehlt: {stueck}')
    offene = {episode_zu_welt.get(o['episode_id']) for o in akte['offen']['eintraege']}
    for welt_id in fall.nicht_offen:
        if welt_id in offene:
            ergebnis.nicht_offen_ok = False
            ergebnis.hinweise.append(f'Noch als offen gezeigt: {welt_id}')
    abgesagt = {episode_zu_welt.get(t['episode_id']) for t in akte['termine']['kommend'] + akte['termine']['vergangen']
                if t['vermutlich_abgesagt']}
    for welt_id in fall.abgesagte_termine:
        if welt_id not in abgesagt:
            ergebnis.termine_ok = False
            ergebnis.hinweise.append(f'Termin nicht als abgesagt gekennzeichnet: {welt_id}')
    return ergebnis


# -- Lage (Ebene 3) ----------------------------------------------------------------

#: Ein Satz, der den überholten Wert nennt und eines dieser Wörter trägt, kennzeichnet ihn als früheren Stand.
_FRUEHER = re.compile(r'\b(vorher|früher|bisher|zuvor|statt|nicht mehr|überholt|ersetzt|verschoben|verlängert|alt(?:e|en|er)?)\b', re.I)


@dataclass
class LageFall:
    """Was die Lage einer Sache im Bericht ergibt."""

    id: str
    status: str
    saetze: list = field(default_factory=list)
    verworfen: int = 0
    falsch: list = field(default_factory=list)
    """Sätze mit verbotener Aussage (überholter Wert als heutiger Stand)."""
    vollstaendig: bool = False
    fehlend: list = field(default_factory=list)
    dauer_ms: float = 0.0


def pruefe_lage(saetze: list[str], fall: Fall) -> tuple[list[str], list[str]]:
    """(falsche Sätze, fehlende Aussagen): Verbotenes ohne Kennzeichnung „vorher“ ist falsch, Erwartetes fehlt sonst."""
    falsch = [satz for satz in saetze
              if any(stueck.casefold() in satz.casefold() for stueck in fall.nicht_aktuell) and not _FRUEHER.search(satz)]
    text = ' \n'.join(saetze).casefold()
    fehlend = [' | '.join(gruppe) for gruppe in fall.aktuell if not any(stueck.casefold() in text for stueck in gruppe)]
    return falsch, fehlend


def lage_messen(akten, episodes, faelle, modell) -> dict:
    """Lage jeder Sache der Fälle erzeugen (mit `modell`, Rolle „hintergrund“) und prüfen.

    Ohne Modell oder mit einem, das nicht lokal ist, wird nichts erzeugt: `gemessen` ist dann falsch
    und der Grund steht im Bericht.
    """
    from icarus_memory.lage import Lagen

    if modell is None:
        return {'gemessen': False, 'grund': 'Kein Modell für die Rolle „hintergrund“ angegeben (--modell-hintergrund).',
                'faelle': []}
    if not getattr(modell, 'is_local', False) or not callable(getattr(modell, 'complete_json', None)):
        return {'gemessen': False, 'faelle': [],
                'grund': 'Das Modell ist nicht lokal oder kann kein JSON; die Lage entsteht nur mit lokalem Modell.'}
    lagen = Lagen(episodes, akten, mindestabstand_s=0)
    ergebnisse = []
    for fall in faelle:
        begonnen = time.perf_counter()
        erzeugt = lagen.erzeugen(fall.sache, modell)
        akte = akten.akte(fall.sache, alle=True) if erzeugt.status in ('erzeugt', 'aktuell') else None
        lage = lagen.lage(fall.sache, akte) if akte else None
        saetze = [s['text'] for s in (lage or {}).get('saetze', [])]
        falsch, fehlend = pruefe_lage(saetze, fall)
        ergebnisse.append(LageFall(fall.id, erzeugt.status, saetze, erzeugt.verworfen, falsch,
                                   bool(saetze) and not fehlend, fehlend if saetze else [' | '.join(g) for g in fall.aktuell],
                                   round((time.perf_counter() - begonnen) * 1000, 1)))
    return {
        'gemessen': True, 'grund': '', 'faelle': ergebnisse,
        'erzeugt': sum(1 for e in ergebnisse if e.saetze), 'gesamt': len(ergebnisse),
        'falsch': sum(len(e.falsch) for e in ergebnisse), 'vollstaendig': sum(e.vollstaendig for e in ergebnisse),
        'saetze': sum(len(e.saetze) for e in ergebnisse), 'verworfen': sum(e.verworfen for e in ergebnisse),
        'modell': f'{getattr(modell, "name", "")} {getattr(modell, "model", "")}'.strip(),
    }


def messen(instanz, aufgenommen, faelle=FAELLE, lage_modell=None) -> dict:
    """Bezüge nachführen, dann jede Akte der Fälle lesen und prüfen. Liefert Zahlen und Fälle.

    Mit `lage_modell` (lokal, Rolle „hintergrund“) wird zusätzlich die Lage jeder Sache erzeugt und geprüft.
    """
    from icarus_memory.akten import Akten
    from icarus_memory.bezuege import Bezuege

    episode_zu_welt = {episode: welt for welt, episode in aufgenommen.episoden.items()}
    # Wie im Betrieb, nur kennt die Messinstanz die Adressen des Nutzers aus der Welt statt aus Konten.
    bezuege = Bezuege(instanz.episodes, workspace=instanz.app.state.workspace, eigene=lambda: list(instanz.eigene))
    akten = Akten(instanz.episodes, bezuege, claims=instanz.claims)
    start = time.perf_counter()
    stand = bezuege.aktualisieren()
    bezuege_s = time.perf_counter() - start
    ergebnisse = []
    for fall in faelle:
        begonnen = time.perf_counter()
        akte = akten.akte(fall.sache, alle=True)
        ergebnis = pruefe(akte, fall, aufgenommen.episoden, episode_zu_welt)
        ergebnis.dauer_ms = round((time.perf_counter() - begonnen) * 1000, 1)
        ergebnisse.append(ergebnis)
    quellen_erwartet = sum(e.quellen_erwartet for e in ergebnisse)
    quellen_gefunden = sum(e.quellen_gefunden for e in ergebnisse)
    lage = lage_messen(akten, instanz.episodes, faelle, lage_modell)
    return {
        'lage': lage,
        'faelle': ergebnisse, 'bezuege_s': round(bezuege_s, 3), 'bezuege_berechnet': stand['berechnet'],
        'quellen_erwartet': quellen_erwartet, 'quellen_gefunden': quellen_gefunden,
        'bestanden': sum(e.bestanden for e in ergebnisse), 'gesamt': len(ergebnisse),
        'sachen': bezuege.sachen(limit=1)['gesamt'],
    }


def markdown(ergebnis: dict) -> str:
    zeilen = ['## Stufe Akten', '',
              f"Bezüge berechnet für {ergebnis['bezuege_berechnet']} Quellen in {ergebnis['bezuege_s']} s; "
              f"{ergebnis['sachen']} Sachen. Einordnung: `RegelEinordnung` (kein Modell).", '',
              f"**{ergebnis['bestanden']} von {ergebnis['gesamt']} Fällen bestanden**, erwartete Quellen im Verlauf: "
              f"{ergebnis['quellen_gefunden']} von {ergebnis['quellen_erwartet']}.", '',
              '| Fall | Quellen | Akte (Quellen gesamt) | aktuell | überholt nicht aktuell | früher sichtbar | nicht offen | Termine | ms |',
              '|---|---|---|---|---|---|---|---|---|']
    ja = lambda wert: 'ja' if wert else '**nein**'  # noqa: E731
    for f in ergebnis['faelle']:
        zeilen.append(f"| {f.id} | {f.quellen_gefunden}/{f.quellen_erwartet} | {f.quellen_gesamt} | {ja(f.aktuell_ok)} | "
                      f"{ja(f.nicht_aktuell_ok)} | {ja(f.fruehere_ok)} | {ja(f.nicht_offen_ok)} | {ja(f.termine_ok)} | {f.dauer_ms} |")
    hinweise = [f'- {f.id}: {h}' for f in ergebnis['faelle'] for h in f.hinweise]
    return '\n'.join(zeilen + ([''] + hinweise if hinweise else []) + [''] + lage_markdown(ergebnis.get('lage'))) + '\n'


def lage_markdown(lage: dict | None) -> list[str]:
    """Abschnitt „Lage“ des Berichts; ohne Modell ausdrücklich „nicht gemessen“."""
    zeilen = ['### Lage (Ebene 3)', '']
    if not lage or not lage['gemessen']:
        grund = lage['grund'] if lage else 'Nicht angefordert.'
        return zeilen + [f'**Nicht gemessen.** {grund}']
    zeilen += [f"Modell (Rolle „hintergrund“): `{lage['modell']}`. Lagen erzeugt für {lage['erzeugt']} von {lage['gesamt']} Sachen, "
               f"{lage['saetze']} Sätze bestanden die Satzprüfung, {lage['verworfen']} wurden verworfen.", '',
               f"**Falsche Aussagen: {lage['falsch']}** (überholter Wert als heutiger Stand); vollständig: "
               f"{lage['vollstaendig']} von {lage['gesamt']}.", '',
               '| Fall | Status | Sätze | verworfen | falsch | vollständig | ms |', '|---|---|---|---|---|---|---|']
    for f in lage['faelle']:
        zeilen.append(f"| {f.id} | {f.status} | {len(f.saetze)} | {f.verworfen} | {len(f.falsch) or 'keine'} | "
                      f"{'ja' if f.vollstaendig else 'nein'} | {f.dauer_ms} |")
    zeilen += [''] + [f'- {f.id}: falsch: „{satz}“' for f in lage['faelle'] for satz in f.falsch]
    zeilen += [f"- {f.id}: fehlt in der Lage: {', '.join(f.fehlend)}" for f in lage['faelle'] if f.saetze and f.fehlend]
    return zeilen
