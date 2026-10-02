"""Terminvorbereitung gegen die Welt: Stichtag 29.09.2026, Termin morgen mit Frau Engel und Herrn Odenthal.

Läuft wie `test_akten.py` gegen die **echte Welt** (`messlatte/welt`), ohne Modell (die Akten sind
deterministisch, die Einordnung ersetzt `RegelEinordnung`). Geprüft wird die Vorbereitung, die das
Morgenbriefing ohne Klick liefert (`terminvorbereitung.vorbereiten`, `tagesbriefing.erstellen`), gegen die
erwarteten Aussagen der Fragen `terminvorbereitung-01`, `-02` und `-04`:

* jede erwartete Aussagengruppe steht im Text der Vorbereitung,
* keine verbotene Aussage (Budget 15.000 statt 12.000) steht darin,
* die erwarteten Belege werden zitiert, verbotene Belege (die Telefonnotiz mit 15.000) nicht.

Frage 03 (Was will Herr Odenthal?) prüft die Antwortstufe; hier nur, dass Herrn Odenthals Wunsch bei ihm
steht und nicht bei Frau Engel. Grenze: Die Akten kennen die Telefonnotiz vom 18.06. nicht (sie hat keine
Adresse); mit dem Modell der Einordnung käme sie hinzu, der neuere Betrag aber bleibt der Stand.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from messlatte.akten import RegelEinordnung
from messlatte.bewertung import fehlende_gruppen, gefundene_verbotene

WELT = Path(__file__).resolve().parents[1] / 'welt'
FRAGEN = ('terminvorbereitung-01', 'terminvorbereitung-02', 'terminvorbereitung-04')


def _pruefsumme() -> str:
    summe = hashlib.sha256()
    for datei in sorted(WELT.rglob('*.json')):
        summe.update(datei.read_bytes())
    return summe.hexdigest()


def _texte(objekt) -> list[str]:
    """Alle Zeichenketten eines verschachtelten Ergebnisses, ohne Kennungen und Zeitstempel."""
    if isinstance(objekt, str):
        return [objekt]
    if isinstance(objekt, dict):
        return [t for k, v in objekt.items() if k not in ('episode_id', 'sache', 'uid', 'adresse') for t in _texte(v)]
    if isinstance(objekt, (list, tuple)):
        return [t for v in objekt for t in _texte(v)]
    return []


def _episoden(objekt) -> set[str]:
    if isinstance(objekt, dict):
        gefunden = {objekt['episode_id']} if isinstance(objekt.get('episode_id'), str) else set()
        return gefunden.union(*(_episoden(v) for v in objekt.values()))
    if isinstance(objekt, (list, tuple)):
        return set().union(*(_episoden(v) for v in objekt))
    return set()


@pytest.fixture(scope='module')
def vorbereitung():
    from icarus_memory import tagesbriefing, terminvorbereitung as tv
    from icarus_memory.akten import Akten
    from icarus_memory.bezuege import Bezuege
    from messlatte.aufnahme import aufnehmen
    from messlatte.daten import Termin
    from messlatte.instanz import instanz_starten
    from messlatte.welt import lade_welt

    vorher = _pruefsumme()
    welt = lade_welt(WELT)
    quelle = next(q for q in welt.quellen if q.id == 'terminvorbereitung-008')
    assert isinstance(quelle, Termin)
    with instanz_starten(stichtag=welt.stichtag, zeitzone=welt.zeitzone, eigene=tuple(welt.nutzer.adressen)) as instanz:
        aufgenommen = aufnehmen(instanz, welt.quellen, welt.stichtag, modell=RegelEinordnung())
        bezuege = Bezuege(instanz.episodes, workspace=instanz.app.state.workspace, eigene=lambda: list(instanz.eigene))
        bezuege.aktualisieren()
        akten = Akten(instanz.episodes, bezuege, claims=instanz.claims)
        episode_id, notiz = tv.termin_im_gedaechtnis(instanz.episodes, 'terminvorbereitung-008')
        # Die Welt legt den Termin ohne Quelle ab; die UID kennt das Gedächtnis aus der Termin-Episode.
        episode_id = episode_id or aufgenommen.episoden['terminvorbereitung-008']
        termin = tv.Termin(
            uid='terminvorbereitung-008', titel=quelle.titel, beginn=quelle.beginn, ende=quelle.ende, ort=quelle.ort,
            teilnehmer=[f'{t.name} <{t.adresse}>' for t in quelle.teilnehmer], notiz=quelle.notiz or notiz,
            episode_id=episode_id)
        ergebnis = tv.vorbereiten(termin, akten=akten, episodes=instanz.episodes, eigene=instanz.eigene,
                                  jetzt=welt.stichtag, workspace=instanz.app.state.workspace)
        lage = tagesbriefing.erstellen([ergebnis], [], None, jetzt=welt.stichtag)
        yield {'welt': welt, 'ergebnis': ergebnis, 'daten': ergebnis.to_dict(), 'lage': lage.to_dict(),
               'zu_welt': {e: w for w, e in aufgenommen.episoden.items()}, 'vorher': vorher}
    assert _pruefsumme() == vorher


def _frage(welt, frage_id: str):
    return next(f for f in welt.fragen if f.id == frage_id)


def _belege(vorbereitung) -> set[str]:
    return {vorbereitung['zu_welt'][e] for e in _episoden(vorbereitung['daten']) if e in vorbereitung['zu_welt']}


@pytest.mark.parametrize('frage_id', FRAGEN)
def test_erwartete_aussagen_stehen_in_der_vorbereitung_und_verbotene_nicht(vorbereitung, frage_id):
    frage = _frage(vorbereitung['welt'], frage_id)
    text = '\n'.join(_texte(vorbereitung['daten']) + _texte(vorbereitung['lage']))
    assert fehlende_gruppen(text, frage.erwartet.aussagen) == (), frage.frage
    assert gefundene_verbotene(text, frage.verboten.aussagen) == (), frage.frage


@pytest.mark.parametrize('frage_id', FRAGEN)
def test_erwartete_belege_werden_zitiert_und_verbotene_nicht(vorbereitung, frage_id):
    frage = _frage(vorbereitung['welt'], frage_id)
    belege = _belege(vorbereitung)
    assert set(frage.erwartet.belege) <= belege, sorted(set(frage.erwartet.belege) - belege)
    assert not set(frage.verboten.belege) & belege


def test_das_budget_ist_12000_und_die_alte_zahl_15000_taucht_nirgends_auf(vorbereitung):
    text = '\n'.join(_texte(vorbereitung['daten']) + _texte(vorbereitung['lage']))
    assert '12.000' in text and '15.000' not in text and '15000' not in text
    engel = next(p for p in vorbereitung['ergebnis'].personen if p.name.endswith('Engel'))
    genannt = [z for z in engel.will if z.rolle == 'genannt']
    assert [vorbereitung['zu_welt'][z.beleg.episode_id] for z in genannt] == ['terminvorbereitung-007']
    assert '12.000 Euro' in genannt[0].text and genannt[0].vermutlich is False


def test_jede_person_hat_ihren_eigenen_wunsch_frau_engel_das_screening_herr_odenthal_die_schulung(vorbereitung):
    personen = {p.name: p for p in vorbereitung['ergebnis'].personen}
    engel, odenthal = personen['Dr. Ruth Engel'], personen['Marcel Odenthal']
    wuensche = lambda p: ' '.join(z.text for z in p.will if z.rolle == 'wunsch')  # noqa: E731
    assert 'Screening' in wuensche(engel) and 'Schulung' not in wuensche(engel)
    assert 'Schulung' in wuensche(odenthal) and 'Screening' not in wuensche(odenthal)
    assert all(z.vermutlich for p in (engel, odenthal) for z in p.will if z.rolle == 'wunsch')


def test_zeit_ort_und_packliste_sind_belegt(vorbereitung):
    daten = vorbereitung['daten']
    assert daten['beginn'].startswith('2026-09-30T14:00') and 'Uferweg 7' in daten['ort']
    assert vorbereitung['zu_welt'][daten['episode_id']] == 'terminvorbereitung-008'
    packen = {vorbereitung['zu_welt'][s['episode_id']]: s['text'] for s in daten['einpacken']}
    assert packen['terminvorbereitung-012'] == 'Laptop, Handout Dysphagiekost mitnehmen.'
    assert 'terminvorbereitung-011' in packen and 'Kalkulation' in packen['terminvorbereitung-011']
    # Was Frau Engel selbst mitbringt („bringe ich folgende Zahlen mit“), ist nicht die Packliste der Nutzerin.
    assert 'terminvorbereitung-010' not in packen


def test_die_tageslage_ist_ein_urteil_in_wenigen_zeilen_mit_aktionen(vorbereitung):
    zeilen = vorbereitung['lage']['zeilen']
    # Ohne Fristen und Wetter bleiben genau die drei Zeilen, die die Welt belegt: Termin, Leute, Einpacken.
    assert [z['art'] for z in zeilen] == ['termin', 'leute', 'einpacken'] and all(z['aktionen'] for z in zeilen)
    assert 'Heute um' not in zeilen[0]['text']  # Stichtag ist der 29.: der Termin ist morgen
    assert zeilen[0]['text'].startswith('Morgen um 14:00 Uhr') and 'Fahrzeit unbekannt' not in zeilen[0]['text']


def test_die_welt_bleibt_unveraendert(vorbereitung):
    assert vorbereitung['vorher'] == _pruefsumme()
    assert isinstance(vorbereitung['welt'].stichtag, datetime)
