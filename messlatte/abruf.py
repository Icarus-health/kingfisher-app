"""Stufe „Abruf“: Was liefert die Suche des Produkts, ohne Modell?

Gefragt wird über `Agent.answer_memory`, die öffentliche Stelle, die auch der
Gesprächsweg des Servers für Gedächtnisfragen aufruft. Darin läuft alles, was
vor der Modellantwort passiert: erste Suchstufe („Was kann Mainz bedeuten?“,
`bedeutungen.py`), Kalender, Wort- und Projektsuche über die eingeordneten
Quellen (`working_memory_answers.prepare` mit `_candidates`) und Bewertung der
Frische.

Das Modell wird durch einen `Kandidatenerfasser` ersetzt: Er sieht genau die
Quellen, die ein Modell sähe, wählt **alle** aus und merkt sich, wie groß der
Kontext war. Damit misst diese Stufe die Suche selbst, nicht die Urteilskraft
eines Modells.

**Grenzen:** Der Weg über `answer_memory` entspricht dem Gespräch nur, wenn das
Produkt die Frage als Gedächtnisfrage erkennt; sonst antwortet es im Betrieb über
den freien Chat mit Werkzeugen (im Ergebnis als `route: chat` vermerkt). Die
Auswahl des Modells (etwa „diese Quelle ist veraltet“) fehlt hier per Konstruktion.
Drei Agent-Hilfen ohne öffentliche Schnittstelle werden gelesen
(`_project_directory`, `_calendar_entries`, `_own_addresses`), damit die Bedeutungen
wie im Produkt berechnet werden.

Die Frage wird zuerst verstanden (`Agent.frage_verstehen`, Rolle „frage“ oder
deterministischer Rückfall); der Bericht weist aus, welcher Weg es war.
"""
from __future__ import annotations

import json
import time
from typing import Iterable

from icarus_memory.providers import ProviderError, Reply

from .aufnahme import ist_rauschen
from .bewertung import ohne_tragende_stelle
from .daten import Frage, Mail, Quelle, Termin
from .ergebnisse import KENNZEICHNUNGEN, AbrufErgebnis, Angebot


class Kandidatenerfasser:
    """Lokaler „Anbieter“, der jede vorgelegte Quelle auswählt und den Kontext misst."""

    name = 'messlatte'
    model = 'kandidatenerfasser'
    is_local = True
    supports_json = True

    def __init__(self) -> None:
        self.kontext_zeichen = 0
        self.anfragen = 0
        self.kontext_quellen = 0
        # Kennungen (S3) der Zeilen, die der Kontext kennzeichnet, nach Art: überholt (Feld `ueberholt`, E2),
        # andere Person, außerhalb des Zeitraums (`kennzeichnung.py`).
        self.gekennzeichnet: dict[str, set[str]] = {art: set() for art in KENNZEICHNUNGEN}
        self.satz_zeichen = 0
        # Was das Modell je Kennung sah (Titel, Stelle, Kontext) in der letzten Anfrage; für „ohne tragende Stelle“.
        self.gezeigt: dict[str, str] = {}

    def complete_json(self, messages, *, max_tokens: int = 256, schema=None) -> Reply:
        from icarus_memory import satzantwort
        if satzantwort.ist_satzanfrage(messages):
            # Die Stufe „Abruf“ misst die Suche, nicht die Sätze; das Produkt fällt auf die Zitate zurück.
            self.satz_zeichen += sum(len(m.get('content', '')) for m in messages)
            raise ProviderError('Sätze werden in der Stufe Abruf nicht gemessen.')
        try:
            quellen = json.loads(messages[-1]['content'])['sources']
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError('Unerwartete Auswahlanfrage') from exc
        self.anfragen += 1
        self.kontext_zeichen += sum(len(m.get('content', '')) for m in messages)
        self.kontext_quellen += sum(1 for q in quellen if str(q.get('id', '')).startswith('S'))
        self.gezeigt = {q['id']: '\n'.join(str(q.get(feld) or '') for feld in ('title', 'text', 'context'))
                        for q in quellen if str(q.get('id', '')).startswith('S')}
        for art, kennungen in self.gekennzeichnet.items():
            kennungen |= {q['id'] for q in quellen if q.get(art)}
        ids = [q['id'] for q in quellen if str(q.get('id', '')).startswith('S')] or \
              [q['id'] for q in quellen]
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': ids}), model=self.model)

    def complete(self, messages, tools) -> Reply:
        raise ProviderError('Der Kandidatenerfasser kennt nur complete_json.')


def quellentext(quelle: Quelle) -> str:
    """Der Volltext einer Weltquelle, so wie er Pflichtaussagen tragen kann (Betreff oder Titel, Text, Ort, Notiz)."""
    if isinstance(quelle, Mail):
        return f'{quelle.betreff}\n{quelle.text}'
    if isinstance(quelle, Termin):
        return f'{quelle.titel}\n{quelle.ort}\n{quelle.notiz}'
    return f'{getattr(quelle, "titel", "")}\n{getattr(quelle, "text", "")}'


def _welt(episode_ids: Iterable[str], rueck: dict) -> tuple:
    """Episoden-IDs in Welt-IDs übersetzen; Reihenfolge bleibt, Doppelte fallen weg."""
    gesehen, ergebnis = set(), []
    for episode_id in episode_ids:
        welt_id = rueck.get(episode_id)
        if welt_id is not None and welt_id not in gesehen:
            gesehen.add(welt_id)
            ergebnis.append(welt_id)
    return tuple(ergebnis)


def _angebot(art: str, label: str, detail: str, ids, rueck: dict) -> Angebot:
    return Angebot(art=art, label=label, detail=detail or '', quellen=_welt(ids or (), rueck))


def _termine(agent, anfrage, rueck: dict) -> tuple:
    """Termine, die das Produkt bei dieser Frage als Bedeutung des Begriffs findet."""
    from icarus_memory.bedeutungen import bedeutungen
    from icarus_memory.frage_weg import hauptsache

    begriff = hauptsache(anfrage)
    if begriff is None:
        return ()
    try:
        gefunden = bedeutungen(begriff, episodes=agent._episodes, projects=agent._project_directory(),
                               entities=getattr(agent._knowledge, 'entities', None),
                               termine=agent._calendar_entries() or [], eigene=agent._own_addresses())
    except Exception:  # noqa: BLE001 - ohne Bedeutungssuche bleibt der Rest der Messung gültig
        return ()
    # Der Kalender des Produkts stellt der Kennung `mac-calendar:` voran; Welt-IDs enthalten keinen Doppelpunkt.
    return tuple(str(m['ref']).split(':')[-1] for m in gefunden['bedeutungen']
                 if m['art'] == 'termin' and m.get('ref'))


def _stellen(frage: Frage, erfasser: Kandidatenerfasser, basis: list, rueck: dict, texte: dict) -> tuple:
    """Erwartete Belege im Kontext, bei denen keine tragende Textstelle zu sehen ist (Welt-IDs)."""
    ohne = []
    for kennung, gezeigt in erfasser.gezeigt.items():
        stelle = int(kennung[1:]) - 1 if kennung[1:].isdigit() else -1
        welt = rueck.get(basis[stelle]) if 0 <= stelle < len(basis) else None
        if welt in frage.erwartet.belege and welt in texte and \
                ohne_tragende_stelle(texte[welt], gezeigt, frage.erwartet.aussagen):
            ohne.append(welt)
    return tuple(ohne)


def abrufen(instanz, frage: Frage, rueck: dict, texte: dict | None = None) -> AbrufErgebnis:
    """Eine Frage an die Suche des Produkts. `rueck` ist Episoden-ID -> Welt-ID.

    `texte` (Welt-ID -> Volltext) braucht nur die Kennzahlen „zu lang“ und „ohne tragende Stelle“; ohne sie bleiben beide leer.
    """
    from icarus_memory.memory_routing import route
    from icarus_memory.working_memory_store import MAX_SOURCE_CHARS

    texte = texte or {}

    start = time.perf_counter()
    erfasser = Kandidatenerfasser()
    try:
        # Wie im Betrieb: erst die Frage verstehen (Rolle „frage“ oder Rückfall), dann Weg und Suche.
        anfrage = instanz.agent.frage_verstehen(frage.frage)
        with instanz.anbieter(erfasser):
            turn = instanz.agent.answer_memory(frage.frage, anfrage=anfrage)
        termine = _termine(instanz.agent, anfrage, rueck)
    except Exception as fehler:  # noqa: BLE001 - jede Frage bekommt ein Ergebnis, auch ein gescheitertes
        return AbrufErgebnis(frage_id=frage.id, weg='fehler', fehler=f'{type(fehler).__name__}: {fehler}',
                             dauer_s=round(time.perf_counter() - start, 3))
    kontext = turn.context or {}
    status = (kontext.get('answer_contract') or {}).get('status', '')
    arbeitsstand = kontext.get('working_answer') or {}
    wahl = kontext.get('meaning_choice')
    kandidaten: tuple = ()
    markiert: tuple = ()
    markiert_nach_art: dict = {}
    angebote: tuple = ()
    abgeschnitten: tuple = ()
    ohne_stelle: tuple = ()
    zaehlung_kuerzung: dict = {}
    if isinstance(wahl, dict):
        weg = 'bedeutungsfrage'
        angebote = tuple(_angebot(o.get('art', ''), o.get('label', ''), o.get('detail', ''), o.get('ids'), rueck)
                         for o in wahl.get('options', []))
        angebote += tuple(_angebot('termin', n.get('label', ''), '', n.get('ids'), rueck)
                          for n in wahl.get('notes', []) if isinstance(n, dict))
    elif kontext.get('mappe_answer'):
        weg = 'gewaehlte_bedeutung'
        angebote = tuple(_angebot('projekt', str(e.get('label', '')), '', e.get('ids'), rueck)
                         for e in kontext['mappe_answer'].get('also_found', []))
    elif arbeitsstand:
        basis = [r.get('episode_id') for r in arbeitsstand.get('basis', []) if isinstance(r, dict)]
        kandidaten = _welt(basis, rueck)
        # Die Kennungen des Kontexts zählen die Basis der Reihe nach (S1 = erster Abschnitt).
        markiert_nach_art = {art: _welt((basis[int(k[1:]) - 1] for k in sorted(kennungen)
                                         if k[1:].isdigit() and 0 < int(k[1:]) <= len(basis)), rueck)
                             for art, kennungen in erfasser.gekennzeichnet.items()}
        markiert = _welt((w for liste in markiert_nach_art.values() for w in liste), rueck)
        suche = arbeitsstand.get('search') or {}
        abgeschnitten = _welt(suche.get('abgeschnitten') or (), rueck)
        zaehlung_kuerzung = suche.get('kuerzung') or {}
        ohne_stelle = _stellen(frage, erfasser, basis, rueck, texte)
        gewaehlt = arbeitsstand.get('meaning_scope')
        weg = 'gewaehlte_bedeutung' if isinstance(gewaehlt, dict) else 'arbeitsstand'
        if isinstance(gewaehlt, dict):
            angebote = (_angebot('gewaehlt', str(gewaehlt.get('label', '')), '', gewaehlt.get('ids'), rueck),)
        angebote += tuple(_angebot('auch_gefunden', str(e.get('label', '')), '', e.get('ids'), rueck)
                          for e in arbeitsstand.get('also_found', []))
    elif kontext.get('answer_mode') == 'calendar_data':
        weg = 'kalender'
    elif status == 'local_only':
        weg = 'nur_lokal'
    else:
        weg = 'unbekannt'
    return AbrufErgebnis(
        frage_id=frage.id, weg=weg, status=status, route=route(frage.frage, working_available=True, anfrage=anfrage),
        verstanden=anfrage.herkunft, verstanden_grund=anfrage.grund, absicht=anfrage.absicht, sachen=tuple(anfrage.sachen),
        kandidaten=kandidaten, davon_rauschen=sum(ist_rauschen(k) for k in kandidaten),
        angebote=angebote, termine_kalender=termine, kontext_zeichen=erfasser.kontext_zeichen,
        abgeschnitten=abgeschnitten, ohne_stelle=ohne_stelle,
        zu_lang=tuple(b for b in frage.erwartet.belege if len(texte.get(b, '')) > MAX_SOURCE_CHARS),
        gekuerzt=int(zaehlung_kuerzung.get('gekuerzt', 0)), absaetze_gezeigt=int(zaehlung_kuerzung.get('absaetze_gezeigt', 0)),
        absaetze_gesamt=int(zaehlung_kuerzung.get('absaetze_gesamt', 0)),
        kontext_quellen=erfasser.kontext_quellen, gekennzeichnet=markiert, gekennzeichnet_nach_art=markiert_nach_art,
        akten_zaehlung=dict((arbeitsstand.get('akten') or {}).get('zaehlung') or {}),
        satz_zeichen=erfasser.satz_zeichen, dauer_s=round(time.perf_counter() - start, 3))
